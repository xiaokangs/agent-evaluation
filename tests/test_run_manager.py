import json
import sys
from pathlib import Path

import pytest

from _helpers import FakeAdapter, make_task
from agents.langgraph_agent import LangGraphAdapter
from core.run_manager import RunManager
from core.schemas import Run
from evaluators.coding import CodingEvaluator

TEST_CMD = f'"{sys.executable}" -m pytest -q -p no:cacheprovider test_solution.py'


def _task(**kw):
    return make_task(validator={"type": "tests_pass", "config": {"command": TEST_CMD}}, **kw)


def test_repeated_runs_validated_and_persisted(tmp_path):
    out = tmp_path / "out"
    mgr = RunManager(out, CodingEvaluator())
    adapter = FakeAdapter("fixer", fix=True)
    runs = mgr.execute(_task(id="fix-off-by-one"), adapter, run_count=2)

    assert [r.run_index for r in runs] == [0, 1]
    assert all(r.validation and r.validation.passed for r in runs)
    # each run used a distinct workspace, removed afterwards
    assert len(set(adapter.seen_workspaces)) == 2
    assert not any(Path(p).exists() for p in adapter.seen_workspaces)

    files = sorted(out.glob("*.json"))
    assert len(files) == 2
    for r in runs:
        f = out / f"fix-off-by-one__fixer__{r.run_id}.json"
        assert f.exists()
        assert Run(**json.loads(f.read_text())) == r


def test_unfixed_workspace_fails_validation(tmp_path):
    mgr = RunManager(tmp_path / "out", CodingEvaluator())
    [run] = mgr.execute(_task(), FakeAdapter("noop", fix=False), run_count=1)
    assert run.validation.passed is False
    assert "tests failed" in run.validation.reason


def test_runs_do_not_contaminate_each_other(tmp_path):
    """A fix in one run must not leak into the next run's workspace."""
    mgr = RunManager(tmp_path / "out", CodingEvaluator())
    task = _task()
    [first] = mgr.execute(task, FakeAdapter("fixer", fix=True))
    [second] = mgr.execute(task, FakeAdapter("noop", fix=False))
    assert first.validation.passed is True
    assert second.validation.passed is False


def test_zero_runs(tmp_path):
    out2 = tmp_path / "out2"
    assert RunManager(out2, CodingEvaluator()).execute(_task(), FakeAdapter(), run_count=0) == []
    assert list(out2.iterdir()) == []


def test_output_dir_created(tmp_path):
    out = tmp_path / "a" / "b"
    RunManager(out, CodingEvaluator())
    assert out.is_dir()


def test_keep_workspaces(tmp_path):
    adapter = FakeAdapter()
    RunManager(tmp_path / "out", CodingEvaluator(), keep_workspaces=True).execute(_task(), adapter)
    ws = Path(adapter.seen_workspaces[0])
    try:
        assert ws.exists()
        assert "sum(range(a, b + 1))" in (ws / "solution.py").read_text()
    finally:
        import shutil
        shutil.rmtree(ws.parent, ignore_errors=True)


def test_adapter_exception_propagates_and_workspace_cleaned(tmp_path):
    adapter = FakeAdapter(raise_exc=RuntimeError("agent crashed"))
    out = tmp_path / "out"
    with pytest.raises(RuntimeError, match="agent crashed"):
        RunManager(out, CodingEvaluator()).execute(_task(), adapter)
    assert not Path(adapter.seen_workspaces[0]).exists()
    assert list(out.iterdir()) == []


def test_langgraph_stub_raises():
    lg = LangGraphAdapter()
    assert lg.agent_id == "langgraph"
    with pytest.raises(NotImplementedError):
        lg.run(make_task(), "/nonexistent", 0)
