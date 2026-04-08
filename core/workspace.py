"""
Workspace isolation utilities.

Each run gets its own directory so runs cannot share mutable state.
Strategy: copy the source workspace into a temp directory per run.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from core.schemas import Task


def prepare_workspace(task: Task, base_dir: Path | None = None) -> Path:
    """
    Create an isolated workspace for one run of `task`.

    Returns the path to the isolated workspace directory.
    Caller is responsible for cleanup (use as context manager via `isolated_workspace`).
    """
    tmp = Path(tempfile.mkdtemp(prefix=f"agent-eval-{task.id}-", dir=base_dir))

    src = Path(task.workspace)
    if not src.exists():
        raise FileNotFoundError(f"Task workspace not found: {src}")

    # Copy workspace contents into tmp
    dest = tmp / "workspace"
    shutil.copytree(src, dest)

    # Run setup commands inside the workspace
    for cmd in task.setup_commands:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=dest,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Setup command failed (exit {result.returncode}): {cmd!r}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

    return dest


def cleanup_workspace(workspace_path: Path) -> None:
    parent = workspace_path.parent   # the tempdir, one level up
    shutil.rmtree(parent, ignore_errors=True)
