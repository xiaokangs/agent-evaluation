"""
Abstract base class for agent adapters.

Each concrete adapter is backend-specific. Adapters must NOT share state
between runs. The run_manager creates a fresh adapter instance per run.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import Run, Task


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
