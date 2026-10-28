import shutil
import sys

import pytest

from _helpers import FIXED_SUM_RANGE, FIXTURES, make_run, make_task
from evaluators.coding import CodingEvaluator

PY = f'"{sys.executable}"'


def _run_in(ws):
    run = make_run(passed=None)
    run.workspace_path = str(ws)
    return run


def _eval(ws, vtype, config):
    task = make_task(validator={"type": vtype, "config": config})
    return CodingEvaluator().evaluate(_run_in(ws), task).validation


def test_no_workspace_path_fails():
    run = make_run(passed=None)
    assert run.workspace_path is None
    out = CodingEvaluator().evaluate(run, make_task())
    assert out is run
    assert out.validation.passed is False
    assert "workspace_path" in out.validation.reason


# ---------------------------------------------------------------- tests_pass / script

def test_tests_pass_success(tmp_path):
    v = _eval(tmp_path, "tests_pass", {"command": f"{PY} -c \"print('ok')\""})
    assert v.passed is True
    assert v.reason == "tests passed"
    assert "ok" in v.details["stdout"]


def test_tests_pass_failure_reports_exit_code(tmp_path):
    v = _eval(tmp_path, "tests_pass", {"command": f"{PY} -c \"import sys; sys.stderr.write('bad'); sys.exit(3)\""})
    assert v.passed is False
    assert "exit 3" in v.reason
    assert "bad" in v.details["stderr"]


def test_tests_pass_runs_in_workspace(tmp_path):
    (tmp_path / "flag.txt").write_text("x")
    v = _eval(tmp_path, "tests_pass", {"command": f"{PY} -c \"open('flag.txt')\""})
    assert v.passed is True


def test_tests_pass_truncates_stdout(tmp_path):
    v = _eval(tmp_path, "tests_pass", {"command": f"{PY} -c \"print('a'*10000)\""})
    assert len(v.details["stdout"]) <= 4000


def test_tests_pass_with_real_fixture(tmp_path):
    ws = tmp_path / "ws"
    shutil.copytree(FIXTURES / "fix-off-by-one", ws, ignore=shutil.ignore_patterns("__pycache__"))
    cmd = f"{PY} -m pytest -q -p no:cacheprovider test_solution.py"
    assert _eval(ws, "tests_pass", {"command": cmd}).passed is False
    (ws / "solution.py").write_text(FIXED_SUM_RANGE)
    assert _eval(ws, "tests_pass", {"command": cmd}).passed is True


def test_script_pass_and_fail(tmp_path):
    ok = _eval(tmp_path, "script", {"script": f"{PY} -c \"pass\""})
    assert ok.passed is True and ok.reason == "validation script passed"
    bad = _eval(tmp_path, "script", {"script": f"{PY} -c \"raise SystemExit(2)\""})
    assert bad.passed is False and "exit 2" in bad.reason


def test_script_requires_script(tmp_path):
    v = _eval(tmp_path, "script", {})
    assert v.passed is False
    assert "requires 'script'" in v.reason


# ---------------------------------------------------------------- output_match

def test_output_match_strips_whitespace(tmp_path):
    v = _eval(tmp_path, "output_match", {"command": f"{PY} -c \"print('  42  ')\"", "expected_output": "42\n"})
    assert v.passed is True
    assert v.details["actual"] == "42"


def test_output_mismatch(tmp_path):
    v = _eval(tmp_path, "output_match", {"command": f"{PY} -c \"print(41)\"", "expected_output": "42"})
    assert v.passed is False
    assert v.details == {"actual": "41", "expected": "42"}


def test_output_match_requires_command(tmp_path):
    v = _eval(tmp_path, "output_match", {"expected_output": "x"})
    assert v.passed is False
    assert "requires 'command'" in v.reason


# ---------------------------------------------------------------- file_changed

def test_file_changed_requires_path(tmp_path):
    v = _eval(tmp_path, "file_changed", {})
    assert v.passed is False and "requires 'path'" in v.reason


def test_file_changed_missing_file(tmp_path):
    v = _eval(tmp_path, "file_changed", {"path": "out.txt"})
    assert v.passed is False and "not found" in v.reason


def test_file_changed_present(tmp_path):
    (tmp_path / "out.txt").write_text("")
    assert _eval(tmp_path, "file_changed", {"path": "out.txt"}).passed is True


def test_file_changed_nested_path(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "x.py").write_text("hello")
    assert _eval(tmp_path, "file_changed", {"path": "sub/x.py", "contains": "ell"}).passed is True


def test_file_changed_contains_mismatch(tmp_path):
    (tmp_path / "out.txt").write_text("hello world")
    v = _eval(tmp_path, "file_changed", {"path": "out.txt", "contains": "bye"})
    assert v.passed is False
    assert v.details == {"expected_contains": "bye"}


def test_unknown_validator_type(tmp_path):
    task = make_task()
    task.validator.type = "bogus"  # bypass enum validation (no validate_assignment)
    v = CodingEvaluator().evaluate(_run_in(tmp_path), task).validation
    assert v.passed is False
    assert "Unknown validator type" in v.reason
