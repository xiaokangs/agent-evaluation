import json
import subprocess
from datetime import timedelta

import pytest

from _helpers import T0, make_task
from agents import codex
from agents.codex import CodexAdapter, _parse_jsonl
from core.schemas import RunStatus, TraceEventKind

T1 = T0 + timedelta(seconds=20)

STREAM = [
    {"type": "thread.started", "thread_id": "abc"},
    {"type": "turn.started"},
    {"type": "item.started", "item": {"id": "1", "type": "command_execution", "command": "ls"}},
    {"type": "item.completed", "item": {"id": "0", "type": "agent_message", "text": "  I will fix it  "}},
    {"type": "item.completed", "item": {"id": "0b", "type": "agent_message", "text": "   "}},
    {"type": "item.completed", "item": {"id": "1", "type": "command_execution", "command": "ls",
                                        "aggregated_output": "solution.py\n", "exit_code": 0}},
    {"type": "item.completed", "item": {"id": "2", "type": "file_change", "changes": [
        {"path": "solution.py", "kind": "update"}, {"path": "new.py", "kind": "create"}]}},
    {"type": "turn.completed", "usage": {"input_tokens": 100, "cached_input_tokens": 50, "output_tokens": 20}},
    {"type": "turn.started"},
    {"type": "turn.completed", "usage": {"input_tokens": 5, "output_tokens": 1}},
    {"type": "error", "message": "boom"},
]


def _stdout(objs):
    return "\n".join(json.dumps(o) for o in objs) + "\nnot json\n\n"


def test_parse_full_stream():
    trace, m = _parse_jsonl(_stdout(STREAM), "", T0, T1, RunStatus.success)
    assert trace.raw_backend == "codex"
    kinds = [e.kind for e in trace.events]
    assert kinds == [
        TraceEventKind.run_start, TraceEventKind.message, TraceEventKind.command,
        TraceEventKind.file_edit, TraceEventKind.file_edit, TraceEventKind.error,
        TraceEventKind.run_end,
    ]
    assert trace.events[1].content == "I will fix it"
    cmd = trace.events[2]
    assert cmd.command == "ls" and cmd.tool_output == "solution.py\n" and cmd.exit_code == 0
    assert [(e.file_path, e.content) for e in trace.events[3:5]] == [
        ("solution.py", "update"), ("new.py", "create")]
    assert trace.events[5].content == "boom"
    assert trace.events[-1].content == "success"

    assert m.turn_count == 2
    assert m.input_tokens == 105
    assert m.output_tokens == 21
    assert m.total_tokens == 126
    assert m.estimated_cost_usd is None
    assert m.tool_call_count == 1
    assert m.wall_clock_seconds == pytest.approx(20.0)


def test_empty_output_marks_everything_unavailable():
    trace, m = _parse_jsonl("", "", T0, T1, RunStatus.failure)
    assert [e.kind for e in trace.events] == [TraceEventKind.run_start, TraceEventKind.run_end]
    assert trace.events[-1].content == "failure"
    assert m.turn_count is None
    assert m.input_tokens is None and m.output_tokens is None and m.total_tokens is None
    assert m.tool_call_count is None
    assert m.estimated_cost_usd is None


def test_error_without_message_uses_whole_object():
    trace, _ = _parse_jsonl(json.dumps({"type": "error", "code": 7}), "", T0, T1, RunStatus.failure)
    err = [e for e in trace.events if e.kind == TraceEventKind.error][0]
    assert "7" in err.content


def test_stderr_appended_before_run_end():
    trace, _ = _parse_jsonl("", "  oops \n", T0, T1, RunStatus.failure)
    assert trace.events[-2].kind == TraceEventKind.error
    assert trace.events[-2].content == "oops"


# ---------------------------------------------------------------- adapter.run

class _Recorder:
    def __init__(self, result=None, exc=None):
        self.result, self.exc, self.calls = result, exc, []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.exc:
            raise self.exc
        return self.result


def _completed(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def test_agent_id():
    assert CodexAdapter().agent_id == "codex"


def test_run_builds_command(monkeypatch, tmp_path):
    rec = _Recorder(_completed(_stdout(STREAM)))
    monkeypatch.setattr(codex.subprocess, "run", rec)
    task = make_task(id="tid", description="please fix", timeout_seconds=7)
    run = CodexAdapter(model="gpt-x", extra_flags=["--bar"]).run(task, str(tmp_path), 1)
    cmd, kw = rec.calls[0]
    assert cmd[:2] == [codex.CODEX_BIN, "exec"]
    for flag in ("--full-auto", "--json", "--skip-git-repo-check", "--bar"):
        assert flag in cmd
    assert cmd[cmd.index("-C") + 1] == str(tmp_path)
    assert cmd[cmd.index("--model") + 1] == "gpt-x"
    assert cmd[-1] == "please fix"
    assert kw["timeout"] == 7

    assert run.status == RunStatus.success
    assert run.agent_id == "codex" and run.task_id == "tid" and run.run_index == 1
    assert run.workspace_path == str(tmp_path)
    assert run.metrics.total_tokens == 126


def test_run_default_timeout(monkeypatch, tmp_path):
    rec = _Recorder(_completed(""))
    monkeypatch.setattr(codex.subprocess, "run", rec)
    CodexAdapter().run(make_task(), str(tmp_path), 0)
    cmd, kw = rec.calls[0]
    assert kw["timeout"] == 300
    assert "--model" not in cmd


def test_nonzero_exit_is_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(codex.subprocess, "run", _Recorder(_completed(_stdout(STREAM), rc=1)))
    run = CodexAdapter().run(make_task(), str(tmp_path), 0)
    assert run.status == RunStatus.failure


def test_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(codex.subprocess, "run",
                        _Recorder(exc=subprocess.TimeoutExpired(cmd="codex", timeout=1)))
    run = CodexAdapter().run(make_task(), str(tmp_path), 0)
    assert run.status == RunStatus.timeout
    assert run.trace.events[-1].content == "timeout"


def test_missing_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(codex, "CODEX_BIN", str(tmp_path / "no-codex-here"))
    with pytest.raises(RuntimeError, match="not found on PATH"):
        CodexAdapter().run(make_task(), str(tmp_path), 0)
