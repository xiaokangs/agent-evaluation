"""
Workspace isolation utilities.

Each run gets its own directory so runs cannot share mutable state.
Strategy: copy the source workspace into a temp directory per run.

Use `isolated_workspace` as a context manager — it guarantees cleanup
even if the process crashes or raises mid-run.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from core.schemas import Task


@contextmanager
def isolated_workspace(
    task: Task,
    keep: bool = False,
    base_dir: Path | None = None,
) -> Generator[Path, None, None]:
    """
    Context manager that creates an isolated workspace, yields it, then
    deletes it — even if an exception is raised inside the block.

    Usage:
        with isolated_workspace(task) as workspace:
            run = adapter.run(task, str(workspace), run_index)
    """
    workspace = _prepare(task, base_dir)
    try:
        yield workspace
    finally:
        if not keep:
            shutil.rmtree(workspace.parent, ignore_errors=True)


def _prepare(task: Task, base_dir: Path | None = None) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=f"agent-eval-{task.id}-", dir=base_dir))

    src = Path(task.workspace)
    if not src.exists():
        raise FileNotFoundError(f"Task workspace not found: {src}")

    dest = tmp / "workspace"
    shutil.copytree(src, dest)

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


# ---------------------------------------------------------------------------
# Legacy helpers kept for backward compatibility
# ---------------------------------------------------------------------------

def prepare_workspace(task: Task, base_dir: Path | None = None) -> Path:
    return _prepare(task, base_dir)


def cleanup_workspace(workspace_path: Path) -> None:
    shutil.rmtree(workspace_path.parent, ignore_errors=True)
