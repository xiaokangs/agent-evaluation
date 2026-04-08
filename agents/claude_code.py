"""
Claude Code agent adapter.

Invokes the `claude` CLI with --output-format stream-json so we get
structured NDJSON events. Parses them into a normalized Trace.

Stream-JSON event types we care about:
  {"type": "assistant", "message": {...}}   — assistant turn with content blocks
  {"type": "tool_use", ...}                 — tool call (inside message content)
  {"type": "result", "subtype": "success"|"error",
   "cost_usd": float, "duration_ms": int, "num_turns": int,
   "total_input_tokens": int, "total_output_tokens": int, ...}
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.schemas import (
    Metrics,
    Run,
    RunStatus,
    Task,
    Trace,
    TraceEvent,
    TraceEventKind,
)
from agents.base import AgentAdapter

# The claude CLI must be on PATH
CLAUDE_BIN = "claude"


class ClaudeCodeAdapter(AgentAdapter):

    def __init__(
        self,
        model: str | None = None,
        extra_flags: list[str] | None = None,
    ) -> None:
        self._model = model
        self._extra_flags = extra_flags or []

    @property
    def agent_id(self) -> str:
        return "claude-code"

    def run(self, task: Task, workspace_path: str, run_index: int) -> Run:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)
        prompt = task.description

        cmd = [
            CLAUDE_BIN,
            "--output-format", "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
            "--print", prompt,
        ]
        if self._model:
            cmd += ["--model", self._model]
        cmd += self._extra_flags

        timeout = task.timeout_seconds or 300
        status = RunStatus.success
        raw_lines: list[str] = []
        stderr = ""

        try:
            proc = subprocess.run(
                cmd,
                cwd=workspace_path,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            raw_lines = [l for l in proc.stdout.splitlines() if l.strip()]
            stderr = proc.stderr
            if proc.returncode != 0 and not raw_lines:
                status = RunStatus.error
        except subprocess.TimeoutExpired:
            status = RunStatus.timeout
        except FileNotFoundError:
            raise RuntimeError(
                f"'{CLAUDE_BIN}' not found on PATH. Install Claude Code CLI first."
            )

        ended_at = datetime.now(timezone.utc)
        trace, metrics = _parse_stream_json(raw_lines, stderr, started_at, ended_at, status)

        return Run(
            run_id=run_id,
            task_id=task.id,
            agent_id=self.agent_id,
            run_index=run_index,
            started_at=started_at,
            ended_at=ended_at,
            status=status,
            workspace_path=workspace_path,
            trace=trace,
            metrics=metrics,
        )


# ---------------------------------------------------------------------------
# Stream-JSON parser
# ---------------------------------------------------------------------------

def _parse_stream_json(
    lines: list[str],
    stderr: str,
    started_at: datetime,
    ended_at: datetime,
    run_status: RunStatus,
) -> tuple[Trace, Metrics]:
    events: list[TraceEvent] = []
    metrics = Metrics()

    # run_start marker
    events.append(TraceEvent(ts=started_at, kind=TraceEventKind.run_start))

    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        event_type = obj.get("type", "")

        if event_type == "assistant":
            msg = obj.get("message", {})
            for block in msg.get("content", []):
                btype = block.get("type")
                if btype == "text":
                    events.append(TraceEvent(
                        ts=ended_at,   # no per-event timestamps in stream-json
                        kind=TraceEventKind.message,
                        role="assistant",
                        content=block.get("text"),
                        raw=block,
                    ))
                elif btype == "tool_use":
                    events.append(TraceEvent(
                        ts=ended_at,
                        kind=TraceEventKind.tool_call,
                        role="assistant",
                        tool_name=block.get("name"),
                        tool_input=block.get("input"),
                        raw=block,
                    ))

        elif event_type == "tool_result":
            events.append(TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.tool_call,
                tool_output=str(obj.get("content", "")),
                raw=obj,
            ))

        elif event_type == "result":
            subtype = obj.get("subtype", "")
            if subtype == "error":
                events.append(TraceEvent(
                    ts=ended_at,
                    kind=TraceEventKind.error,
                    content=obj.get("result"),
                    raw=obj,
                ))

            # Extract metrics from the result event.
            # Actual field names from stream-json:
            #   duration_ms, num_turns, total_cost_usd
            #   usage.input_tokens, usage.output_tokens
            duration_ms = obj.get("duration_ms")
            usage = obj.get("usage", {})
            input_tokens = usage.get("input_tokens")
            output_tokens = usage.get("output_tokens")
            total_tokens = (
                (input_tokens or 0) + (output_tokens or 0)
            ) or None
            metrics = Metrics(
                wall_clock_seconds=(duration_ms / 1000.0) if duration_ms is not None else
                    (ended_at - started_at).total_seconds(),
                turn_count=obj.get("num_turns"),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=obj.get("total_cost_usd"),
                tool_call_count=sum(
                    1 for e in events if e.kind == TraceEventKind.tool_call and e.tool_name
                ),
            )

        elif event_type == "system":
            # Informational — skip or store as raw
            pass

    if stderr.strip():
        events.append(TraceEvent(
            ts=ended_at,
            kind=TraceEventKind.error,
            content=stderr.strip(),
        ))

    if not metrics.wall_clock_seconds:
        metrics = metrics.model_copy(update={
            "wall_clock_seconds": (ended_at - started_at).total_seconds()
        })

    # run_end marker
    events.append(TraceEvent(
        ts=ended_at,
        kind=TraceEventKind.run_end,
        content=run_status.value,
    ))

    return Trace(raw_backend="claude-code", events=events), metrics
