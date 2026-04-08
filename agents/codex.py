"""
Codex agent adapter.

Invokes:  codex exec --full-auto --json --skip-git-repo-check -C <workspace> "<prompt>"

--full-auto      non-interactive, workspace-write sandbox
--json           emit events as JSONL on stdout (structured trace)
--skip-git-repo-check  allow running outside a git repo

JSONL event types we handle:
  {"type": "AgentMessage", "role": "assistant", "content": [...]}
  {"type": "ToolCallStart", "tool_name": "...", "args": {...}}
  {"type": "ToolCallEnd", "tool_name": "...", "output": "..."}
  {"type": "SessionConfigured", ...}
  {"type": "Error", "message": "..."}

Token usage and cost are not available from the Codex CLI and remain None.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone

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

CODEX_BIN = "codex"


class CodexAdapter(AgentAdapter):

    def __init__(self, model: str | None = None, extra_flags: list[str] | None = None) -> None:
        self._model = model
        self._extra_flags = extra_flags or []

    @property
    def agent_id(self) -> str:
        return "codex"

    def run(self, task: Task, workspace_path: str, run_index: int) -> Run:
        run_id = str(uuid.uuid4())
        started_at = datetime.now(timezone.utc)

        cmd = [
            CODEX_BIN, "exec",
            "--full-auto",
            "--json",
            "--skip-git-repo-check",
            "-C", workspace_path,
        ]
        if self._model:
            cmd += ["--model", self._model]
        cmd += self._extra_flags
        cmd.append(task.description)

        timeout = task.timeout_seconds or 300
        status = RunStatus.success
        stdout = ""
        stderr = ""

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            if proc.returncode != 0:
                status = RunStatus.failure
        except subprocess.TimeoutExpired:
            status = RunStatus.timeout
        except FileNotFoundError:
            raise RuntimeError(
                f"'{CODEX_BIN}' not found on PATH. Install the Codex CLI first."
            )

        ended_at = datetime.now(timezone.utc)
        trace = _parse_jsonl(stdout, stderr, started_at, ended_at, status)
        metrics = Metrics(
            wall_clock_seconds=(ended_at - started_at).total_seconds(),
            tool_call_count=sum(
                1 for e in trace.events
                if e.kind == TraceEventKind.tool_call and e.tool_name
            ),
            # Token usage and cost not available from Codex CLI
        )

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


def _parse_jsonl(
    stdout: str,
    stderr: str,
    started_at: datetime,
    ended_at: datetime,
    run_status: RunStatus,
) -> Trace:
    events: list[TraceEvent] = [
        TraceEvent(ts=started_at, kind=TraceEventKind.run_start),
    ]

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            # Plain text line — capture as message
            events.append(TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.message,
                role="assistant",
                content=line,
            ))
            continue

        etype = obj.get("type", "")

        if etype == "AgentMessage":
            content_blocks = obj.get("content", [])
            text = " ".join(
                b.get("text", "") for b in content_blocks if b.get("type") == "text"
            ) if isinstance(content_blocks, list) else str(content_blocks)
            if text.strip():
                events.append(TraceEvent(
                    ts=ended_at,
                    kind=TraceEventKind.message,
                    role="assistant",
                    content=text,
                    raw=obj,
                ))

        elif etype in ("ToolCallStart", "ToolCall"):
            events.append(TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.tool_call,
                tool_name=obj.get("tool_name") or obj.get("name"),
                tool_input=obj.get("args") or obj.get("input"),
                raw=obj,
            ))

        elif etype == "ToolCallEnd":
            events.append(TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.tool_call,
                tool_name=obj.get("tool_name"),
                tool_output=str(obj.get("output", "")),
                raw=obj,
            ))

        elif etype == "Error":
            events.append(TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.error,
                content=obj.get("message") or str(obj),
                raw=obj,
            ))

        # SessionConfigured and other informational events are ignored

    if stderr.strip():
        events.append(TraceEvent(
            ts=ended_at,
            kind=TraceEventKind.error,
            content=stderr.strip(),
        ))

    events.append(TraceEvent(
        ts=ended_at,
        kind=TraceEventKind.run_end,
        content=run_status.value,
    ))

    return Trace(raw_backend="codex", events=events)
