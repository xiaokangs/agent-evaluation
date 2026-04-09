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
    Create an isolated workspace for one run of `task`, yield it, then
    delete it — even if an exception is raised inside the block.

    Usage:
        with isolated_workspace(task) as workspace:
            run = adapter.run(task, str(workspace), run_index)
    """
    tmp = Path(tempfile.mkdtemp(prefix=f"agent-eval-{task.id}-", dir=base_dir))

    src = Path(task.workspace)
    if not src.exists():
        raise FileNotFoundError(f"Task workspace not found: {src}")

    workspace = tmp / "workspace"
    shutil.copytree(src, workspace)

    for cmd in task.setup_commands:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            shutil.rmtree(tmp, ignore_errors=True)
            raise RuntimeError(
                f"Setup command failed (exit {result.returncode}): {cmd!r}\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

    try:
        yield workspace
    finally:
        if not keep:
            shutil.rmtree(tmp, ignore_errors=True)
