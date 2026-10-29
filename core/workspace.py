"""
Workspace isolation utilities.

Each run gets its own directory so runs cannot share mutable state.
Strategy: copy the source workspace into a temp directory per run.

Use `isolated_workspace` as a context manager — the temp directory is
removed if copying or setup fails, and when the `with` block exits
(normally or by raising). Cleanup cannot happen if the process itself is
killed (e.g. SIGKILL), so stray `agent-eval-*` temp dirs are possible then.
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
    src = Path(task.workspace)
    if not src.exists():
        raise FileNotFoundError(f"Task workspace not found: {src}")

    tmp = Path(tempfile.mkdtemp(prefix=f"agent-eval-{task.id}-", dir=base_dir))
    # Set once setup succeeds: `keep` only preserves workspaces that were
    # actually handed to the caller; failed setups are always removed.
    ready = False
    try:
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
                raise RuntimeError(
                    f"Setup command failed (exit {result.returncode}): {cmd!r}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}"
                )

        ready = True
        yield workspace
    finally:
        if not (keep and ready):
            shutil.rmtree(tmp, ignore_errors=True)
