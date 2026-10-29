"""
Abstract base class for agent adapters.

Each concrete adapter is backend-specific. cli.py builds one adapter
instance per agent and reuses it across all tasks and runs (RunManager does
not create adapters), so adapters must NOT keep mutable state between
run() calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import Run, Task


def _to_text(data: str | bytes | None) -> str:
    """Normalize TimeoutExpired.stdout/stderr, which may be bytes even with text=True."""
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


class AgentAdapter(ABC):
    """
    Minimal interface every agent adapter must implement.
    """

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Stable identifier for this agent backend (e.g. 'claude-code', 'codex')."""

    @abstractmethod
    def run(self, task: Task, workspace_path: str, run_index: int) -> Run:
        """
        Execute the task in the given isolated workspace.

        The workspace is already set up (copied + setup_commands executed) by
        the run_manager before this is called.

        Must return a fully populated Run (including trace and metrics).
        Fields that cannot be observed must be left as None, not fabricated.
        """
