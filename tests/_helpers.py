"""Shared helpers for tests (fake adapters, run factories)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from agents.base import AgentAdapter
from core.schemas import (
    Metrics,
    Run,
    RunStatus,
    Task,
    Trace,
    TraceEvent,
    TraceEventKind,
    ValidationResult,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES = REPO_ROOT / "datasets" / "fixtures"
TASKS_DIR = REPO_ROOT / "datasets" / "tasks"

FIXED_SUM_RANGE = (
    "def sum_range(a: int, b: int) -> int:\n"
    "    return sum(range(a, b + 1))\n"
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_task(**overrides) -> Task:
    data = {
        "id": "t1",
        "description": "do the thing",
        "workspace": str(FIXTURES / "fix-off-by-one"),
        "validator": {"type": "file_changed", "config": {"path": "solution.py"}},
    }
    data.update(overrides)
    return Task(**data)


def make_run(
    agent_id: str = "a",
    task_id: str = "t",
    run_index: int = 0,
    passed: bool | None = True,
    reason: str | None = None,
    wall: float | None = 1.0,
    tokens: int | None = 100,
    cost: float | None = 0.01,
    turns: int | None = 2,
    tools: int | None = 3,
    with_metrics: bool = True,
    with_trace: bool = False,
) -> Run:
    return Run(
        run_id=str(uuid.uuid4()),
        task_id=task_id,
        agent_id=agent_id,
        run_index=run_index,
        started_at=T0,
        ended_at=T0 + timedelta(seconds=wall or 0),
        status=RunStatus.success,
        metrics=Metrics(
            wall_clock_seconds=wall,
            total_tokens=tokens,
            estimated_cost_usd=cost,
            turn_count=turns,
            tool_call_count=tools,
        ) if with_metrics else None,
        validation=(
            ValidationResult(passed=passed, reason=reason) if passed is not None else None
        ),
        trace=Trace(
            raw_backend=agent_id,
            events=[TraceEvent(ts=T0, kind=TraceEventKind.run_start)],
        ) if with_trace else None,
    )


class FakeAdapter(AgentAdapter):
    """Adapter that optionally edits the workspace, never calls a real agent."""

    def __init__(self, agent_id: str = "fake", fix: bool = True, raise_exc: Exception | None = None):
        self._id = agent_id
        self.fix = fix
        self.raise_exc = raise_exc
        self.seen_workspaces: list[str] = []

    @property
    def agent_id(self) -> str:
        return self._id

    def run(self, task: Task, workspace_path: str, run_index: int) -> Run:
        self.seen_workspaces.append(workspace_path)
        if self.raise_exc is not None:
            raise self.raise_exc
        ws = Path(workspace_path)
        if self.fix:
            (ws / "solution.py").write_text(FIXED_SUM_RANGE)
            (ws / "DONE.txt").write_text("ok")
        now = datetime.now(timezone.utc)
        return Run(
            run_id=str(uuid.uuid4()),
            task_id=task.id,
            agent_id=self.agent_id,
            run_index=run_index,
            started_at=now,
            ended_at=now,
            status=RunStatus.success,
            workspace_path=workspace_path,
            trace=Trace(raw_backend=self._id, events=[TraceEvent(ts=now, kind=TraceEventKind.run_start)]),
            metrics=Metrics(wall_clock_seconds=1.5, turn_count=1, total_tokens=10, tool_call_count=1),
        )
