"""
Coding task evaluators.

Dispatches to the correct sub-evaluator based on ValidatorType.
All evaluators are deterministic — no LLM judges.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from core.schemas import Run, Task, ValidationResult, ValidatorType
from evaluators.base import Evaluator


class CodingEvaluator(Evaluator):

    def evaluate(self, run: Run, task: Task) -> Run:
        vtype = task.validator.type
        cfg = task.validator.config
        workspace = run.workspace_path

        if workspace is None:
            run.validation = ValidationResult(
                passed=False,
                reason="workspace_path not set on run — cannot validate",
            )
            return run

        if vtype == ValidatorType.tests_pass:
            run.validation = self._tests_pass(workspace, cfg)
        elif vtype == ValidatorType.output_match:
            run.validation = self._output_match(workspace, cfg)
        elif vtype == ValidatorType.file_changed:
            run.validation = self._file_changed(workspace, cfg)
        elif vtype == ValidatorType.script:
            run.validation = self._script(workspace, cfg)
        else:
            run.validation = ValidationResult(
                passed=False,
                reason=f"Unknown validator type: {vtype}",
            )
        return run

    def _tests_pass(self, workspace: str, cfg: dict) -> ValidationResult:
        cmd = cfg.get("command", "pytest")
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=cfg.get("timeout_seconds", 120),
        )
        passed = result.returncode == 0
        return ValidationResult(
            passed=passed,
            reason="tests passed" if passed else f"tests failed (exit {result.returncode})",
            details={"stdout": result.stdout[-4000:], "stderr": result.stderr[-2000:]},
        )

    def _output_match(self, workspace: str, cfg: dict) -> ValidationResult:
        cmd = cfg.get("command")
        expected = cfg.get("expected_output", "")
        if not cmd:
            return ValidationResult(passed=False, reason="output_match validator requires 'command'")
        result = subprocess.run(
            cmd, shell=True, cwd=workspace, capture_output=True, text=True,
            timeout=cfg.get("timeout_seconds", 60),
        )
        actual = result.stdout.strip()
        passed = actual == expected.strip()
        return ValidationResult(
            passed=passed,
            reason="output matched" if passed else "output did not match expected",
            details={"actual": actual, "expected": expected},
        )

    def _file_changed(self, workspace: str, cfg: dict) -> ValidationResult:
        path = cfg.get("path")
        if not path:
            return ValidationResult(passed=False, reason="file_changed validator requires 'path'")
        full = Path(workspace) / path
        if not full.exists():
            return ValidationResult(passed=False, reason=f"File not found: {path}")
        contains = cfg.get("contains")
        if contains and contains not in full.read_text():
            return ValidationResult(
                passed=False,
                reason=f"File {path} does not contain expected string",
                details={"expected_contains": contains},
            )
        return ValidationResult(passed=True, reason=f"File {path} present and valid")

    def _script(self, workspace: str, cfg: dict) -> ValidationResult:
        script = cfg.get("script")
        if not script:
            return ValidationResult(passed=False, reason="script validator requires 'script'")
        result = subprocess.run(
            script, shell=True, cwd=workspace, capture_output=True, text=True,
            timeout=cfg.get("timeout_seconds", 120),
        )
        passed = result.returncode == 0
        return ValidationResult(
            passed=passed,
            reason="validation script passed" if passed else f"validation script failed (exit {result.returncode})",
            details={"stdout": result.stdout[-4000:], "stderr": result.stderr[-2000:]},
        )
