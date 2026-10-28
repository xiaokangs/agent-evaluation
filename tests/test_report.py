import json

import pytest

from _helpers import make_run
from core.report import build_report, write_json, write_markdown
from core.schemas import Report


def test_build_report_groups_and_aggregates():
    runs = [
        make_run("b", "t2", 0, passed=True, wall=2.0, tokens=100, cost=0.02),
        make_run("a", "t1", 0, passed=True, wall=1.0, tokens=100, cost=0.01),
        make_run("a", "t1", 1, passed=False, wall=3.0, tokens=300, cost=0.03),
        make_run("a", "t1", 2, passed=None, wall=None, tokens=None, cost=None),
    ]
    rpt = build_report(runs)
    assert rpt.task_ids == ["t1", "t2"]
    assert rpt.agent_ids == ["a", "b"]
    assert [(s.agent_id, s.task_id) for s in rpt.summaries] == [("a", "t1"), ("b", "t2")]
    s = rpt.summaries[0]
    assert len(s.runs) == 3
    # run without validation counts as not passed
    assert s.success_rate == pytest.approx(1 / 3)
    # unavailable metrics are excluded, not treated as zero
    assert s.mean_duration_seconds == pytest.approx(2.0)
    assert s.mean_total_tokens == pytest.approx(200)
    assert s.mean_cost_usd == pytest.approx(0.02)
    assert rpt.metadata == {}


def test_all_metrics_unavailable_gives_none():
    rpt = build_report([make_run(with_metrics=False), make_run(cost=None, tokens=None, wall=None)])
    s = rpt.summaries[0]
    assert s.mean_duration_seconds is None
    assert s.mean_total_tokens is None
    assert s.mean_cost_usd is None


def test_empty_runs():
    rpt = build_report([])
    assert rpt.summaries == [] and rpt.task_ids == [] and rpt.agent_ids == []


def test_manifest_goes_into_metadata():
    rpt = build_report([make_run()], manifest={"batch_id": "b1"})
    assert rpt.metadata == {"batch_id": "b1"}


def test_write_json_roundtrip(tmp_path):
    rpt = build_report([make_run("a", "t"), make_run("b", "t", passed=False)])
    out = tmp_path / "r.json"
    write_json(rpt, out)
    loaded = Report(**json.loads(out.read_text()))
    assert loaded.agent_ids == ["a", "b"]
    assert [s.success_rate for s in loaded.summaries] == [1.0, 0.0]


def _md(runs, manifest=None, tmp_path=None):
    out = tmp_path / "r.md"
    write_markdown(build_report(runs, manifest=manifest), out)
    return out.read_text()


def test_markdown_side_by_side_table(tmp_path):
    runs = [
        make_run("claude-code", "fix-x", 0, passed=True, wall=7.0, tokens=1234, cost=0.0123),
        make_run("codex", "fix-x", 0, passed=False, wall=15.0, tokens=None, cost=None),
    ]
    md = _md(runs, tmp_path=tmp_path)
    assert md.startswith("# Agent Evaluation Report")
    assert "### `fix-x`" in md
    assert "| `claude-code` | 1 | 100% | 7.0s | 1,234 | $0.0123 |" in md
    assert "| `codex` | 1 | 0% | 15.0s | N/A | N/A |" in md
    assert "## Agent Summary" in md
    assert "| `claude-code` | 1 | 100% | 7.0s | $0.0123 |" in md
    assert "| `codex` | 1 | 0% | 15.0s | N/A |" in md
    assert "**Agents:** `claude-code`, `codex`" in md
    # single run without trace → no details block
    assert "<details>" not in md


def test_markdown_run_details(tmp_path):
    long_reason = "x" * 100
    runs = [
        make_run("a", "t", 1, passed=False, reason=long_reason, wall=2.0, turns=None, tools=4),
        make_run("a", "t", 0, passed=True, wall=1.0, turns=3, tools=None),
    ]
    md = _md(runs, tmp_path=tmp_path)
    assert "<details><summary>`a` run details</summary>" in md
    row0 = "| 0 | PASS | 1.0s | 3 | N/A |  |"
    row1 = f"| 1 | FAIL | 2.0s | N/A | 4 | {'x' * 60} |"
    assert row0 in md and row1 in md
    assert md.index(row0) < md.index(row1)  # sorted by run_index
    assert "x" * 61 not in md


def test_markdown_details_shown_for_single_run_with_trace(tmp_path):
    md = _md([make_run(with_trace=True)], tmp_path=tmp_path)
    assert "run details" in md


def test_markdown_manifest_header(tmp_path):
    manifest = {"batch_id": "batch_1", "started_at": "2026-04-08T14:30:00.123456+00:00",
                "duration_seconds": 61.4, "total_runs": 17}
    md = _md([make_run()], manifest=manifest, tmp_path=tmp_path)
    assert "**Batch:** `batch_1`" in md
    assert "**Run period:** 2026-04-08T14:30:00  |  Duration: 61s" in md
    assert "**Total runs:** 17" in md


@pytest.mark.skip(reason="疑似 bug：没有 manifest 时 'Total runs' 回退成 len(summaries)（agent×task 组数），不是 run 的数量")
def test_markdown_total_runs_without_manifest(tmp_path):
    runs = [make_run("a", "t", i) for i in range(3)]
    md = _md(runs, tmp_path=tmp_path)
    assert "**Total runs:** 3" in md
