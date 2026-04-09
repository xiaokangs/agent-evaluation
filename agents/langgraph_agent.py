"""
LangGraph agent adapter (stub).

P1 target. This adapter wraps a custom LangGraph-based coding agent.

The LangGraph agent will be developed in a separate project and invoked
here either as:
  - a subprocess (e.g. `python langgraph_runner.py --task <json>`)
  - an in-process call if the agent is importable as a library

Key advantages of LangGraph for evaluation purposes:
  - explicit node/edge graph → rich step-level trace
  - controllable retry and recovery loops
  - inspectable state at each step

Compared to productized agents (Claude Code, Codex), a LangGraph agent
will expose more trace granularity but require more instrumentation effort.
Fields that are not available from the agent remain None — not fabricated.
"""

from __future__ import annotations

from core.schemas import Run, Task
from agents.base import AgentAdapter


class LangGraphAdapter(AgentAdapter):

    def __init__(self) -> None:
        # TODO (P1): accept config — runner path, model, graph definition, etc.
        pass

    @property
    def agent_id(self) -> str:
        return "langgraph"

    def run(self, task: Task, workspace_path: str, run_index: int) -> Run:
        raise NotImplementedError(
            "LangGraphAdapter is a P1 stub. "
            "Implement once the LangGraph agent project is ready."
        )
