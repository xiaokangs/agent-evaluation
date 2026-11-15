"""Validation integrity and batch robustness (see docs/feature-request.md).

Non-skipped tests cover current behaviour that should survive the proposed
fixes. Skipped tests describe the desired behaviour for the suspected bugs
listed in docs/feature-request.md; un-skip them when the fix lands.
"""

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

import cli
from _helpers import FIXTURES, FakeAdapter, make_run, make_task
from agents.langgraph_agent import LangGraphAdapter
from core.run_manager import RunManager
from core.schemas import Run, Task, ValidationResult
from evaluators.base import Evaluator
from evaluators.coding import CodingEvaluator

PY = f'"{sys.executable}"'
TEST_CMD = f"{PY} -m pytest -q -p no:cacheprovider test_solution.py"
runner = CliRunner()


def _eval(ws, vtype, config):
    task = make_task(validator={"type": vtype, "config": config})
    run = make_run(passed=None)
    run.workspace_path = str(ws)
    return CodingEvaluator().evaluate(run, task).validation


def _tests_task(**kw):
    return make_task(validator={"type": "tests_pass", "config": {"command": TEST_CMD}}, **kw)


class TamperingAdapter(FakeAdapter):
    """Leaves solution.py broken and replaces the tests with an always-passing one."""

    def run(self, task, workspace_path, run_index):
        out = super().run(task, workspace_path, run_index)
        (Path(workspace_path) / "test_solution.py").write_text("def test_ok():\n    assert True\n")
        return out


class RecordingEvaluator(Evaluator):
    def __init__(self):
        self.seen: list[tuple[str, bool]] = []

    def evaluate(self, run: Run, task: Task) -> Run:
        ws = run.workspace_path or ""
        self.seen.append((ws, Path(ws).is_dir()))
        run.validation = ValidationResult(passed=True, reason="recorded")
        return run


class BoomEvaluator(Evaluator):
    def evaluate(self, run: Run, task: Task) -> Run:
        raise RuntimeError("validator exploded")


# ---------------------------------------------------------------- evaluator details

def test_output_match_default_expected_is_empty(tmp_path):
    v = _eval(tmp_path, "output_match", {"command": f'{PY} -c "pass"'})
    assert v.passed is True
    assert v.details == {"actual": "", "expected": ""}


def test_output_match_runs_in_workspace(tmp_path):
    (tmp_path / "data.txt").write_text("hello\n")
    v = _eval(tmp_path, "output_match", {
        "command": f"{PY} -c \"print(open('data.txt').read())\"", "expected_output": "hello",
    })
    assert v.passed is True


def test_tests_pass_keeps_tail_of_stdout(tmp_path):
    v = _eval(tmp_path, "tests_pass", {"command": f"{PY} -c \"print('a'*5000); print('END')\""})
    assert v.passed is True
    assert len(v.details["stdout"]) <= 4000
    assert v.details["stdout"].rstrip().endswith("END")


def test_script_truncates_stderr(tmp_path):
    v = _eval(tmp_path, "script", {"script": f"{PY} -c \"import sys; sys.stderr.write('e'*5000)\""})
    assert v.passed is True
    assert 0 < len(v.details["stderr"]) <= 2000


def test_file_changed_empty_contains_is_ignored(tmp_path):
    (tmp_path / "out.txt").write_text("anything")
    assert _eval(tmp_path, "file_changed", {"path": "out.txt", "contains": ""}).passed is True


def test_evaluate_preserves_other_run_fields(tmp_path):
    run = make_run(agent_id="x", task_id="y", run_index=4, passed=None)
    run.workspace_path = str(tmp_path)
    (tmp_path / "solution.py").write_text("")
    out = CodingEvaluator().evaluate(run, make_task())
    assert out is run
    assert (out.agent_id, out.task_id, out.run_index) == ("x", "y", 4)
    assert out.metrics is not None and out.metrics.total_tokens == 100
    assert out.validation.passed is True


# ---------------------------------------------------------------- run manager

def test_evaluator_sees_live_workspace_before_cleanup(tmp_path):
    ev = RecordingEvaluator()
    [run] = RunManager(tmp_path / "out", ev).execute(_tests_task(), FakeAdapter())
    [(ws, existed)] = ev.seen
    assert existed is True
    assert (Path(ws) / "solution.py").exists() is False  # removed after the run
    assert run.validation.reason == "recorded"


def test_persisted_filename_and_content(tmp_path):
    out = tmp_path / "out"
    [run] = RunManager(out, CodingEvaluator()).execute(_tests_task(id="my-task"), FakeAdapter("agentA"))
    [f] = list(out.glob("*.json"))
    assert f.name == f"my-task__agentA__{run.run_id}.json"
    data = json.loads(f.read_text())
    assert data["validation"]["passed"] is True
    assert data["agent_id"] == "agentA"


def test_evaluator_failure_still_cleans_workspace(tmp_path):
    adapter = FakeAdapter()
    try:
        RunManager(tmp_path / "out", BoomEvaluator()).execute(_tests_task(), adapter)
    except RuntimeError:
        pass
    assert adapter.seen_workspaces
    assert not Path(adapter.seen_workspaces[0]).exists()


def test_genuine_fix_passes_and_fixture_untouched(tmp_path):
    before = (FIXTURES / "fix-off-by-one" / "test_solution.py").read_text()
    [run] = RunManager(tmp_path / "out", CodingEvaluator()).execute(_tests_task(), FakeAdapter(fix=True))
    assert run.validation.passed is True
    assert (FIXTURES / "fix-off-by-one" / "test_solution.py").read_text() == before
    assert not (FIXTURES / "fix-off-by-one" / "DONE.txt").exists()


def test_tampering_never_modifies_source_fixture(tmp_path):
    before = (FIXTURES / "fix-off-by-one" / "test_solution.py").read_text()
    RunManager(tmp_path / "out", CodingEvaluator()).execute(_tests_task(), TamperingAdapter(fix=False))
    assert (FIXTURES / "fix-off-by-one" / "test_solution.py").read_text() == before


# ---------------------------------------------------------------- CLI with langgraph

def _one_task_dir(d):
    d.mkdir()
    (d / "t.json").write_text(json.dumps({
        "id": "t", "description": "d", "workspace": str(FIXTURES / "fix-off-by-one"),
        "validator": {"type": "file_changed", "config": {"path": "DONE.txt"}},
    }))


def test_batch_with_langgraph_does_not_report_success(monkeypatch, tmp_path):
    agents = {"fixer": FakeAdapter("fixer"), "langgraph": LangGraphAdapter()}
    monkeypatch.setattr(cli, "_build_adapter_map", lambda: agents)
    tasks = tmp_path / "tasks"
    _one_task_dir(tasks)
    res = runner.invoke(cli.app, ["batch", "--agents", "fixer,langgraph", "--tasks-dir", str(tasks),
                                  "--output-dir", str(tmp_path / "out"), "--batch-id", "b"])
    assert res.exit_code != 0
    assert "Batch complete" not in res.output


def test_run_with_langgraph_does_not_report_done(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "_build_adapter_map", lambda: {"langgraph": LangGraphAdapter()})
    tasks = tmp_path / "tasks"
    _one_task_dir(tasks)
    res = runner.invoke(cli.app, ["run", "--task", str(tasks / "t.json"), "--agents", "langgraph",
                                  "--output-dir", str(tmp_path / "out")])
    assert res.exit_code != 0
    assert "Done." not in res.output


# ---------------------------------------------------------------- suspected bugs (desired behaviour)

@pytest.mark.skip(reason="疑似 bug: tests_pass 在 agent 可编辑的 workspace 里跑测试，"
                         "agent 把 test_solution.py 换成恒过的测试也能 PASS（docs/feature-request.md P0）")
def test_replaced_tests_do_not_pass(tmp_path):
    [run] = RunManager(tmp_path / "out", CodingEvaluator()).execute(_tests_task(), TamperingAdapter(fix=False))
    assert run.validation.passed is False


@pytest.mark.skip(reason="疑似 bug: output_match 不检查退出码，`printf expected; exit 9` 也 PASS")
def test_output_match_requires_zero_exit(tmp_path):
    v = _eval(tmp_path, "output_match", {
        "command": f"{PY} -c \"print('42'); raise SystemExit(9)\"", "expected_output": "42",
    })
    assert v.passed is False


@pytest.mark.skip(reason="疑似 bug: file_changed 只看文件存在，agent 没改 solution.py 也 PASS")
def test_file_changed_requires_actual_change(tmp_path):
    task = make_task(validator={"type": "file_changed", "config": {"path": "solution.py"}})
    [run] = RunManager(tmp_path / "out", CodingEvaluator()).execute(task, FakeAdapter(fix=False))
    assert run.validation.passed is False


@pytest.mark.skip(reason="疑似 bug: 验证超时抛 TimeoutExpired 直接打断整个 batch，没有记成失败")
def test_validator_timeout_recorded_as_failure(tmp_path):
    task = make_task(validator={"type": "script", "config": {
        "script": f"{PY} -c \"import time; time.sleep(3)\"", "timeout_seconds": 0.2}})
    [run] = RunManager(tmp_path / "out", CodingEvaluator()).execute(task, FakeAdapter())
    assert run.validation.passed is False


@pytest.mark.skip(reason="疑似 bug: 某次 adapter 抛异常后 batch 中断，已保存的结果没有 manifest.json")
def test_batch_writes_manifest_despite_adapter_failure(monkeypatch, tmp_path):
    agents = {"fixer": FakeAdapter("fixer"), "boom": FakeAdapter("boom", raise_exc=RuntimeError("x"))}
    monkeypatch.setattr(cli, "_build_adapter_map", lambda: agents)
    tasks = tmp_path / "tasks"
    _one_task_dir(tasks)
    runner.invoke(cli.app, ["batch", "--agents", "fixer,boom", "--tasks-dir", str(tasks),
                            "--output-dir", str(tmp_path / "out"), "--batch-id", "b"])
    assert (tmp_path / "out" / "b" / "manifest.json").exists()
