"""
Codex agent adapter.

Invokes:  codex exec --full-auto --json --skip-git-repo-check -C <workspace> "<prompt>"

--full-auto            non-interactive, workspace-write sandbox
--json                 emit events as JSONL on stdout (structured trace)
--skip-git-repo-check  allow running outside a git repo

JSONL event schema (verified against codex v0.118.0):
  {"type": "thread.started", "thread_id": "..."}
  {"type": "turn.started"}
  {"type": "item.started",   "item": {"id": "...", "type": "<item_type>", ...}}
  {"type": "item.completed", "item": {"id": "...", "type": "<item_type>", ...}}
  {"type": "turn.completed", "usage": {"input_tokens": N, "cached_input_tokens": N, "output_tokens": N}}

item types:
  agent_message      — text reasoning from the agent
  command_execution  — shell command with aggregated_output and exit_code
  file_change        — file edits with list of {path, kind}

Cost is not exposed by the Codex CLI and remains None.
tool_call_count counts only command_execution items (Claude Code counts every
tool_use block). If no JSON event is parsed at all, turn/token/tool counts are
None (unavailable); otherwise observed zeros are reported as 0.
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
from agents.base import AgentAdapter, _to_text

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
        except subprocess.TimeoutExpired as e:
            status = RunStatus.timeout
            # Keep whatever the agent emitted before the timeout for debugging.
            stdout = _to_text(e.stdout)
            stderr = _to_text(e.stderr)
        except FileNotFoundError:
            raise RuntimeError(
                f"'{CODEX_BIN}' not found on PATH. Install the Codex CLI first."
            )

        ended_at = datetime.now(timezone.utc)
        trace, metrics = _parse_jsonl(stdout, stderr, started_at, ended_at, status)
        if status == RunStatus.timeout:
            trace.events.insert(len(trace.events) - 1, TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.timeout,
                content=f"timed out after {timeout}s",
            ))

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
) -> tuple[Trace, Metrics]:
    """Parse Codex exec --json JSONL output (schema: see the module docstring)."""
    events: list[TraceEvent] = [
        TraceEvent(ts=started_at, kind=TraceEventKind.run_start),
    ]

    # Counts are only meaningful if at least one JSON event was parsed; with no
    # events at all, metrics are unavailable (None) rather than 0.
    saw_event = False
    turn_count = 0
    total_input_tokens = 0
    total_output_tokens = 0
    command_count = 0

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        saw_event = True
        etype = obj.get("type", "")

        if etype == "turn.started":
            turn_count += 1

        elif etype == "turn.completed":
            usage = obj.get("usage", {})
            total_input_tokens += usage.get("input_tokens", 0)
            total_output_tokens += usage.get("output_tokens", 0)

        elif etype == "item.completed":
            item = obj.get("item", {})
            itype = item.get("type", "")

            if itype == "agent_message":
                text = item.get("text", "").strip()
                if text:
                    events.append(TraceEvent(
                        ts=ended_at,
                        kind=TraceEventKind.message,
                        role="assistant",
                        content=text,
                        raw=item,
                    ))

            elif itype == "command_execution":
                command_count += 1
                events.append(TraceEvent(
                    ts=ended_at,
                    kind=TraceEventKind.command,
                    command=item.get("command"),
                    tool_output=item.get("aggregated_output"),
                    exit_code=item.get("exit_code"),
                    raw=item,
                ))

            elif itype == "file_change":
                for change in item.get("changes", []):
                    events.append(TraceEvent(
                        ts=ended_at,
                        kind=TraceEventKind.file_edit,
                        file_path=change.get("path"),
                        content=change.get("kind"),  # "update" | "create" | "delete"
                        raw=item,
                    ))

        elif etype == "error":
            events.append(TraceEvent(
                ts=ended_at,
                kind=TraceEventKind.error,
                content=obj.get("message") or str(obj),
                raw=obj,
            ))

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

    total_tokens = total_input_tokens + total_output_tokens
    metrics = Metrics(
        wall_clock_seconds=(ended_at - started_at).total_seconds(),
        turn_count=turn_count if saw_event else None,
        input_tokens=total_input_tokens if saw_event else None,
        output_tokens=total_output_tokens if saw_event else None,
        total_tokens=total_tokens if saw_event else None,
        estimated_cost_usd=None,   # not exposed by Codex CLI
        tool_call_count=command_count if saw_event else None,
    )

    return Trace(raw_backend="codex", events=events), metrics
