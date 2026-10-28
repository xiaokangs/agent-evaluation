"""CLI integration: run / batch / report wired together with fake (offline) agents."""

import json
import sys

import pytest
from typer.testing import CliRunner

import cli
from _helpers import FIXTURES, REPO_ROOT, FakeAdapter, make_run
from core.schemas import Report

runner = CliRunner()
TEST_CMD = f'"{sys.executable}" -m pytest -q -p no:cacheprovider test_solution.py'


@pytest.fixture
def fake_agents(monkeypatch):
    agents = {"fixer": FakeAdapter("fixer", fix=True), "noop": FakeAdapter("noop", fix=False)}
    monkeypatch.setattr(cli, "_build_adapter_map", lambda: agents)
    return agents


def test_real_adapter_map_ids():
    m = cli._build_adapter_map()
    assert set(m) == {"claude-code", "codex", "langgraph"}
    for key, adapter in m.items():
        assert adapter.agent_id == key


def test_resolve_agents_strips_whitespace(fake_agents):
    adapters = cli._resolve_agents(" fixer , noop")
    assert [a.agent_id for a in adapters] == ["fixer", "noop"]


def test_run_unknown_agent_exits_1(fake_agents, tmp_path):
    res = runner.invoke(cli.app, [
        "run", "--task", str(REPO_ROOT / "datasets/tasks/example_fix_bug.json"),
        "--agents", "nope", "--output-dir", str(tmp_path / "out"),
    ])
    assert res.exit_code == 1
    assert "Unknown agent" in res.output
    assert not (tmp_path / "out").exists()


def test_run_with_shipped_task_file(fake_agents, tmp_path, monkeypatch, python_on_path):
    # task JSON uses repo-relative workspace paths and `python -m pytest`
    monkeypatch.chdir(REPO_ROOT)
    out = tmp_path / "out"
    res = runner.invoke(cli.app, [
        "run", "--task", "datasets/tasks/example_fix_bug.json",
        "--agents", "fixer,noop", "--runs", "2", "--output-dir", str(out),
    ])
    assert res.exit_code == 0, res.output
    assert "PASS" in res.output and "FAIL" in res.output
    runs = [json.loads(f.read_text()) for f in out.glob("*.json")]
    assert len(runs) == 4
    by_agent = {}
    for r in runs:
        assert r["task_id"] == "fix-off-by-one"
        by_agent.setdefault(r["agent_id"], []).append(r["validation"]["passed"])
    assert by_agent == {"fixer": [True, True], "noop": [False, False]}


def _write_tasks(d):
    d.mkdir()
    ws = str(FIXTURES / "fix-off-by-one")
    (d / "a_tests.json").write_text(json.dumps({
        "id": "task-tests", "description": "fix", "workspace": ws,
        "validator": {"type": "tests_pass", "config": {"command": TEST_CMD}},
    }))
    (d / "b_file.json").write_text(json.dumps({
        "id": "task-file", "description": "write DONE", "workspace": ws,
        "validator": {"type": "file_changed", "config": {"path": "DONE.txt", "contains": "ok"}},
    }))
    (d / "notes.txt").write_text("ignored")


def test_batch_then_report(fake_agents, tmp_path):
    tasks_dir = tmp_path / "tasks"
    _write_tasks(tasks_dir)
    out = tmp_path / "results"
    res = runner.invoke(cli.app, [
        "batch", "--agents", "fixer,noop", "--runs", "2",
        "--tasks-dir", str(tasks_dir), "--output-dir", str(out), "--batch-id", "b1",
    ])
    assert res.exit_code == 0, res.output
    batch_dir = out / "b1"
    manifest = json.loads((batch_dir / "manifest.json").read_text())
    assert manifest["batch_id"] == "b1"
    assert manifest["agents"] == ["fixer", "noop"]
    assert manifest["task_ids"] == ["task-tests", "task-file"]
    assert manifest["runs_per_agent_per_task"] == 2
    assert manifest["total_runs"] == 8
    assert manifest["passed"] == 4
    assert manifest["failed"] == 4
    assert manifest["duration_seconds"] >= 0
    assert len([f for f in batch_dir.glob("*.json") if f.name != "manifest.json"]) == 8

    # markdown report
    md_path = tmp_path / "report.md"
    res = runner.invoke(cli.app, ["report", "--input-dir", str(batch_dir), "--output", str(md_path)])
    assert res.exit_code == 0, res.output
    md = md_path.read_text()
    assert "**Batch:** `b1`" in md
    assert "**Total runs:** 8" in md
    assert "### `task-tests`" in md and "### `task-file`" in md
    assert "| `fixer` | 2 | 100% |" in md
    assert "| `noop` | 2 | 0% |" in md

    # json report
    js_path = tmp_path / "report.json"
    res = runner.invoke(cli.app, ["report", "--input-dir", str(batch_dir), "--output", str(js_path)])
    assert res.exit_code == 0, res.output
    rpt = Report(**json.loads(js_path.read_text()))
    assert rpt.agent_ids == ["fixer", "noop"]
    assert rpt.task_ids == ["task-file", "task-tests"]
    rates = {(s.agent_id, s.task_id): s.success_rate for s in rpt.summaries}
    assert rates == {
        ("fixer", "task-file"): 1.0, ("fixer", "task-tests"): 1.0,
        ("noop", "task-file"): 0.0, ("noop", "task-tests"): 0.0,
    }
    assert rpt.metadata["batch_id"] == "b1"


def test_batch_auto_batch_id(fake_agents, tmp_path):
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "t.json").write_text(json.dumps({
        "id": "t", "description": "d", "workspace": str(FIXTURES / "fix-off-by-one"),
        "validator": {"type": "file_changed", "config": {"path": "DONE.txt"}},
    }))
    out = tmp_path / "results"
    res = runner.invoke(cli.app, ["batch", "--agents", "fixer", "--tasks-dir", str(tasks_dir),
                                  "--output-dir", str(out)])
    assert res.exit_code == 0, res.output
    [batch_dir] = list(out.iterdir())
    assert batch_dir.name.startswith("batch_")
    assert json.loads((batch_dir / "manifest.json").read_text())["passed"] == 1


def test_batch_no_tasks_exits_1(fake_agents, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    res = runner.invoke(cli.app, ["batch", "--agents", "fixer", "--tasks-dir", str(empty),
                                  "--output-dir", str(tmp_path / "out")])
    assert res.exit_code == 1
    assert "No task files" in res.output


def test_batch_unknown_agent_exits_1(fake_agents, tmp_path):
    tasks_dir = tmp_path / "tasks"
    _write_tasks(tasks_dir)
    res = runner.invoke(cli.app, ["batch", "--agents", "fixer,ghost", "--tasks-dir", str(tasks_dir),
                                  "--output-dir", str(tmp_path / "out")])
    assert res.exit_code == 1


def test_report_empty_dir_exits_1(tmp_path):
    res = runner.invoke(cli.app, ["report", "--input-dir", str(tmp_path), "--output",
                                  str(tmp_path / "r.md")])
    assert res.exit_code == 1
    assert not (tmp_path / "r.md").exists()


def test_report_only_manifest_exits_1(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    res = runner.invoke(cli.app, ["report", "--input-dir", str(tmp_path), "--output",
                                  str(tmp_path / "r.md")])
    assert res.exit_code == 1


def test_report_without_manifest(tmp_path):
    d = tmp_path / "runs"
    d.mkdir()
    for r in [make_run("a", "t", 0), make_run("b", "t", 0, passed=False)]:
        (d / f"{r.task_id}__{r.agent_id}__{r.run_id}.json").write_text(r.model_dump_json())
    out = tmp_path / "r.md"
    res = runner.invoke(cli.app, ["report", "--input-dir", str(d), "--output", str(out)])
    assert res.exit_code == 0, res.output
    md = out.read_text()
    assert "**Batch:**" not in md
    assert "| `a` | 1 | 100% |" in md
    assert "| `b` | 1 | 0% |" in md
