import json
import subprocess
from datetime import timedelta

import pytest

from _helpers import T0, make_task
from agents import claude_code
from agents.claude_code import ClaudeCodeAdapter, _parse_stream_json
from core.schemas import RunStatus, TraceEventKind

T1 = T0 + timedelta(seconds=12)


def _lines(*objs):
    return [json.dumps(o) for o in objs]


ASSISTANT = {
    "type": "assistant",
    "message": {"content": [
        {"type": "text", "text": "Looking at the bug"},
        {"type": "tool_use", "name": "Edit", "input": {"file_path": "solution.py"}},
        {"type": "thinking", "thinking": "ignored"},
    ]},
}
RESULT = {
    "type": "result", "subtype": "success",
    "duration_ms": 7000, "num_turns": 3, "total_cost_usd": 0.05,
    "modelUsage": {
        "m1": {"inputTokens": 10, "outputTokens": 5, "cacheReadInputTokens": 100,
               "cacheCreationInputTokens": 20},
        "m2": {"inputTokens": 1, "outputTokens": 1},
    },
}


def test_parse_full_stream():
    lines = _lines({"type": "system", "subtype": "init"}, ASSISTANT,
                   {"type": "tool_result", "content": "done"}, RESULT)
    lines.insert(1, "not json at all")
    trace, m = _parse_stream_json(lines, "", T0, T1, RunStatus.success)

    assert trace.raw_backend == "claude-code"
    kinds = [e.kind for e in trace.events]
    assert kinds == [
        TraceEventKind.run_start, TraceEventKind.message, TraceEventKind.tool_call,
        TraceEventKind.tool_call, TraceEventKind.run_end,
    ]
    assert trace.events[0].ts == T0
    msg = trace.events[1]
    assert msg.role == "assistant" and msg.content == "Looking at the bug"
    tool = trace.events[2]
    assert tool.tool_name == "Edit" and tool.tool_input == {"file_path": "solution.py"}
    assert trace.events[3].tool_output == "done"
    assert trace.events[-1].content == "success"

    assert m.wall_clock_seconds == pytest.approx(7.0)
    assert m.turn_count == 3
    assert m.input_tokens == 11
    assert m.output_tokens == 6
    assert m.total_tokens == 11 + 6 + 100 + 20
    assert m.estimated_cost_usd == pytest.approx(0.05)
    # tool_result events have no tool_name and are not counted as calls
    assert m.tool_call_count == 1


def test_parse_without_result_leaves_metrics_unavailable():
    trace, m = _parse_stream_json(_lines(ASSISTANT), "", T0, T1, RunStatus.success)
    assert m.wall_clock_seconds == pytest.approx(12.0)
    assert m.turn_count is None
    assert m.total_tokens is None
    assert m.input_tokens is None
    assert m.estimated_cost_usd is None
    assert m.tool_call_count is None


def test_result_without_usage_or_duration():
    _, m = _parse_stream_json(_lines({"type": "result", "subtype": "success"}), "", T0, T1,
                              RunStatus.success)
    assert m.wall_clock_seconds == pytest.approx(12.0)
    assert m.input_tokens is None and m.output_tokens is None and m.total_tokens is None
    assert m.tool_call_count == 0


def test_result_error_and_stderr_become_error_events():
    lines = _lines({"type": "result", "subtype": "error", "result": "it broke"})
    trace, _ = _parse_stream_json(lines, "  warn  \n", T0, T1, RunStatus.error)
    errors = [e for e in trace.events if e.kind == TraceEventKind.error]
    assert [e.content for e in errors] == ["it broke", "warn"]
    assert trace.events[-1].kind == TraceEventKind.run_end
    assert trace.events[-1].content == "error"


def test_empty_stream_has_start_and_end_markers():
    trace, _ = _parse_stream_json([], "", T0, T1, RunStatus.timeout)
    assert [e.kind for e in trace.events] == [TraceEventKind.run_start, TraceEventKind.run_end]
    assert trace.events[-1].content == "timeout"


# ---------------------------------------------------------------- adapter.run (subprocess mocked)

class _Recorder:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc
        self.calls = []

    def __call__(self, cmd, **kw):
        self.calls.append((cmd, kw))
        if self.exc:
            raise self.exc
        return self.result


def _completed(stdout="", stderr="", rc=0):
    return subprocess.CompletedProcess(args=[], returncode=rc, stdout=stdout, stderr=stderr)


def test_agent_id():
    assert ClaudeCodeAdapter().agent_id == "claude-code"


def test_run_builds_command_and_parses(monkeypatch, tmp_path):
    rec = _Recorder(_completed("\n".join(_lines(ASSISTANT, RESULT)) + "\n\n"))
    monkeypatch.setattr(claude_code.subprocess, "run", rec)
    task = make_task(id="tid", description="fix it please", timeout_seconds=42)
    run = ClaudeCodeAdapter(model="opus", extra_flags=["--foo"]).run(task, str(tmp_path), 2)

    cmd, kw = rec.calls[0]
    assert cmd[0] == claude_code.CLAUDE_BIN
    assert cmd[cmd.index("--output-format") + 1] == "stream-json"
    assert cmd[cmd.index("--print") + 1] == "fix it please"
    assert cmd[cmd.index("--model") + 1] == "opus"
    assert cmd[-1] == "--foo"
    assert kw["cwd"] == str(tmp_path)
    assert kw["timeout"] == 42

    assert run.task_id == "tid" and run.agent_id == "claude-code" and run.run_index == 2
    assert run.status == RunStatus.success
    assert run.workspace_path == str(tmp_path)
    assert run.metrics.turn_count == 3
    assert run.ended_at >= run.started_at
    assert run.validation is None


def test_run_default_timeout_and_no_model(monkeypatch, tmp_path):
    rec = _Recorder(_completed(""))
    monkeypatch.setattr(claude_code.subprocess, "run", rec)
    ClaudeCodeAdapter().run(make_task(), str(tmp_path), 0)
    cmd, kw = rec.calls[0]
    assert "--model" not in cmd
    assert kw["timeout"] == 300


def test_nonzero_exit_without_output_is_error(monkeypatch, tmp_path):
    monkeypatch.setattr(claude_code.subprocess, "run", _Recorder(_completed("", "auth failed", rc=1)))
    run = ClaudeCodeAdapter().run(make_task(), str(tmp_path), 0)
    assert run.status == RunStatus.error
    assert any(e.kind == TraceEventKind.error and e.content == "auth failed" for e in run.trace.events)


def test_nonzero_exit_with_output_keeps_success(monkeypatch, tmp_path):
    out = "\n".join(_lines(RESULT))
    monkeypatch.setattr(claude_code.subprocess, "run", _Recorder(_completed(out, rc=1)))
    run = ClaudeCodeAdapter().run(make_task(), str(tmp_path), 0)
    assert run.status == RunStatus.success


def test_timeout(monkeypatch, tmp_path):
    monkeypatch.setattr(claude_code.subprocess, "run",
                        _Recorder(exc=subprocess.TimeoutExpired(cmd="claude", timeout=1)))
    run = ClaudeCodeAdapter().run(make_task(), str(tmp_path), 0)
    assert run.status == RunStatus.timeout
    assert run.trace.events[-1].content == "timeout"
    assert run.metrics.wall_clock_seconds is not None


def test_missing_binary_raises_runtime_error(monkeypatch, tmp_path):
    monkeypatch.setattr(claude_code, "CLAUDE_BIN", str(tmp_path / "definitely-not-claude"))
    with pytest.raises(RuntimeError, match="not found on PATH"):
        ClaudeCodeAdapter().run(make_task(), str(tmp_path), 0)
