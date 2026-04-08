"""
Core data schemas for agent-eval.

These are the shared contracts between all layers of the system.
Do not add workload-specific or agent-specific logic here.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

class ValidatorType(str, Enum):
    tests_pass = "tests_pass"
    output_match = "output_match"
    file_changed = "file_changed"
    script = "script"


class ValidatorConfig(BaseModel):
    type: ValidatorType
    # Flexible config interpreted by the matching evaluator
    config: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    id: str
    description: str
    # Path to workspace to copy for isolation, or a git repo URL
    workspace: str
    validator: ValidatorConfig
    # Optional shell commands to run inside the workspace before the agent starts
    setup_commands: list[str] = Field(default_factory=list)
    timeout_seconds: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------

class TraceEventKind(str, Enum):
    run_start = "run_start"
    run_end = "run_end"
    message = "message"
    tool_call = "tool_call"
    file_edit = "file_edit"
    command = "command"
    validation = "validation"
    error = "error"
    timeout = "timeout"


class TraceEvent(BaseModel):
    ts: datetime
    kind: TraceEventKind
    # Normalized fields — may be None if the agent backend cannot expose them
    role: str | None = None          # "assistant" | "user" | "system"
    content: str | None = None
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    tool_output: str | None = None
    file_path: str | None = None
    command: str | None = None
    exit_code: int | None = None
    raw: dict[str, Any] | None = None   # Backend-specific payload, kept for debugging


class Trace(BaseModel):
    raw_backend: str          # Name of the backend that produced this trace
    events: list[TraceEvent]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class Metrics(BaseModel):
    wall_clock_seconds: float | None = None
    turn_count: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    tool_call_count: int | None = None
    # Fields that were unavailable are explicitly None rather than defaulted to 0


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class RunStatus(str, Enum):
    success = "success"
    failure = "failure"
    timeout = "timeout"
    error = "error"


class ValidationResult(BaseModel):
    passed: bool
    reason: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Run(BaseModel):
    run_id: str
    task_id: str
    agent_id: str
    run_index: int      # 0-based index within repeated runs for the same (task, agent) pair
    started_at: datetime
    ended_at: datetime | None = None
    status: RunStatus | None = None
    workspace_path: str | None = None    # Path to the isolated workspace used
    trace: Trace | None = None
    metrics: Metrics | None = None
    validation: ValidationResult | None = None
    artifacts: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class AgentTaskSummary(BaseModel):
    agent_id: str
    task_id: str
    runs: list[Run]
    # Computed across all runs
    success_rate: float | None = None
    mean_duration_seconds: float | None = None
    mean_total_tokens: float | None = None
    mean_cost_usd: float | None = None


class Report(BaseModel):
    generated_at: datetime
    task_ids: list[str]
    agent_ids: list[str]
    summaries: list[AgentTaskSummary]
    metadata: dict[str, Any] = Field(default_factory=dict)
