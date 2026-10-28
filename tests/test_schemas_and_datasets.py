import json
import shutil
import subprocess
import sys

import pytest
from pydantic import ValidationError

from _helpers import TASKS_DIR, make_run
from core.schemas import Metrics, Run, Task, ValidatorType

TASK_FILES = sorted(TASKS_DIR.glob("*.json"))
REPO_ROOT = TASKS_DIR.parent.parent


# --------------------------------------------------------------------------- schemas

def test_task_minimal_defaults():
    t = Task(id="x", description="d", workspace="w", validator={"type": "tests_pass"})
    assert t.setup_commands == []
    assert t.timeout_seconds is None
    assert t.metadata == {}
    assert t.validator.type is ValidatorType.tests_pass
    assert t.validator.config == {}


def test_task_rejects_unknown_validator_type():
    with pytest.raises(ValidationError):
        Task(id="x", description="d", workspace="w", validator={"type": "llm_judge"})


def test_task_requires_core_fields():
    with pytest.raises(ValidationError):
        Task(id="x", workspace="w", validator={"type": "tests_pass"})  # type: ignore[call-arg]


def test_metrics_unavailable_fields_are_none_not_zero():
    m = Metrics()
    for field in Metrics.model_fields:
        assert getattr(m, field) is None


def test_run_json_roundtrip():
    run = make_run(with_trace=True, reason="r")
    again = Run(**json.loads(run.model_dump_json()))
    assert again == run


# --------------------------------------------------------------------------- datasets

def test_there_are_task_files():
    assert len(TASK_FILES) >= 9


@pytest.mark.parametrize("path", TASK_FILES, ids=lambda p: p.name)
def test_task_file_is_valid_and_workspace_exists(path):
    task = Task(**json.loads(path.read_text()))
    ws = REPO_ROOT / task.workspace
    assert ws.is_dir(), f"{task.workspace} missing"
    assert (ws / "solution.py").is_file()
    assert (ws / "test_solution.py").is_file()
    assert task.description.strip()


def test_task_ids_are_unique():
    ids = [json.loads(p.read_text())["id"] for p in TASK_FILES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("path", TASK_FILES, ids=lambda p: p.name)
def test_fixture_fails_before_agent_touches_it(path, tmp_path):
    """README: a fixture must FAIL untouched, otherwise the task is trivially solved."""
    task = Task(**json.loads(path.read_text()))
    ws = tmp_path / "ws"
    shutil.copytree(REPO_ROOT / task.workspace, ws,
                    ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_solution.py"],
        cwd=ws, capture_output=True, text=True, timeout=60,
    )
    assert proc.returncode not in (0, 5), proc.stdout + proc.stderr
