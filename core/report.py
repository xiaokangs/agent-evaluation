"""
Report generation: aggregates runs into a side-by-side comparison.
"""

from __future__ import annotations

import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.schemas import AgentTaskSummary, Report, Run


def build_report(runs: list[Run], manifest: dict[str, Any] | None = None) -> Report:
    """Aggregate a flat list of runs into a Report."""
    groups: dict[tuple[str, str], list[Run]] = {}
    for run in runs:
        key = (run.agent_id, run.task_id)
        groups.setdefault(key, []).append(run)

    summaries: list[AgentTaskSummary] = []
    for (agent_id, task_id), group_runs in sorted(groups.items()):
        successes = [r for r in group_runs if r.validation and r.validation.passed]
        durations = [
            r.metrics.wall_clock_seconds
            for r in group_runs
            if r.metrics and r.metrics.wall_clock_seconds is not None
        ]
        tokens = [
            r.metrics.total_tokens
            for r in group_runs
            if r.metrics and r.metrics.total_tokens is not None
        ]
        costs = [
            r.metrics.estimated_cost_usd
            for r in group_runs
            if r.metrics and r.metrics.estimated_cost_usd is not None
        ]

        summaries.append(AgentTaskSummary(
            agent_id=agent_id,
            task_id=task_id,
            runs=group_runs,
            success_rate=len(successes) / len(group_runs) if group_runs else None,
            mean_duration_seconds=statistics.mean(durations) if durations else None,
            mean_total_tokens=statistics.mean(tokens) if tokens else None,
            mean_cost_usd=statistics.mean(costs) if costs else None,
        ))

    meta: dict[str, Any] = manifest or {}

    return Report(
        generated_at=datetime.now(timezone.utc),
        task_ids=sorted({r.task_id for r in runs}),
        agent_ids=sorted({r.agent_id for r in runs}),
        summaries=summaries,
        metadata=meta,
    )


def write_json(report: Report, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2))


def write_markdown(report: Report, path: Path) -> None:
    meta = report.metadata
    lines: list[str] = ["# Agent Evaluation Report", ""]

    if meta.get("batch_id"):
        lines += [f"**Batch:** `{meta['batch_id']}`", ""]
    lines += [f"**Generated:** {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}", ""]

    if meta.get("started_at"):
        dur = meta.get("duration_seconds")
        dur_str = f"  |  Duration: {dur:.0f}s" if dur else ""
        lines += [f"**Run period:** {meta['started_at'][:19]}{dur_str}", ""]

    lines += [
        f"**Agents:** {', '.join(f'`{a}`' for a in report.agent_ids)}",
        f"**Tasks:** {len(report.task_ids)}  |  "
        f"**Total runs:** {meta.get('total_runs', sum(len(s.runs) for s in report.summaries))}",
        "",
        "---",
        "",
    ]

    # --- Per-task side-by-side table ---
    lines += ["## Results by Task", ""]

    for task_id in report.task_ids:
        task_summaries = [s for s in report.summaries if s.task_id == task_id]
        lines += [f"### `{task_id}`", ""]
        lines.append("| Agent | Runs | Pass | Duration | Tokens | Cost |")
        lines.append("|-------|------|------|----------|--------|------|")
        for s in task_summaries:
            sr = f"{s.success_rate:.0%}" if s.success_rate is not None else "N/A"
            dur = f"{s.mean_duration_seconds:.1f}s" if s.mean_duration_seconds is not None else "N/A"
            tok = f"{s.mean_total_tokens:,.0f}" if s.mean_total_tokens is not None else "N/A"
            cost = f"${s.mean_cost_usd:.4f}" if s.mean_cost_usd is not None else "N/A"
            lines.append(f"| `{s.agent_id}` | {len(s.runs)} | {sr} | {dur} | {tok} | {cost} |")

        # Per-run trace summary
        for s in task_summaries:
            if len(s.runs) > 1 or any(r.trace for r in s.runs):
                lines += ["", f"<details><summary>`{s.agent_id}` run details</summary>", ""]
                lines.append("| Run | Result | Duration | Turns | Tools | Failure |")
                lines.append("|-----|--------|----------|-------|-------|---------|")
                for r in sorted(s.runs, key=lambda x: x.run_index):
                    passed = r.validation.passed if r.validation else None
                    result = "PASS" if passed else "FAIL"
                    dur = f"{r.metrics.wall_clock_seconds:.1f}s" if r.metrics and r.metrics.wall_clock_seconds else "N/A"
                    turns = str(r.metrics.turn_count) if r.metrics and r.metrics.turn_count is not None else "N/A"
                    tools = str(r.metrics.tool_call_count) if r.metrics and r.metrics.tool_call_count is not None else "N/A"
                    reason = ""
                    if r.validation and not r.validation.passed:
                        reason = (r.validation.reason or "")[:60]
                    lines.append(f"| {r.run_index} | {result} | {dur} | {turns} | {tools} | {reason} |")
                lines += ["", "</details>", ""]
        lines.append("")

    # --- Agent aggregate summary ---
    lines += ["---", "", "## Agent Summary", ""]
    lines.append("| Agent | Tasks | Overall Pass Rate | Mean Duration | Mean Cost |")
    lines.append("|-------|-------|-------------------|---------------|-----------|")

    for agent_id in report.agent_ids:
        agent_summaries = [s for s in report.summaries if s.agent_id == agent_id]
        all_runs_agent = [r for s in agent_summaries for r in s.runs]
        passed = sum(1 for r in all_runs_agent if r.validation and r.validation.passed)
        overall_rate = f"{passed / len(all_runs_agent):.0%}" if all_runs_agent else "N/A"

        durations = [r.metrics.wall_clock_seconds for r in all_runs_agent
                     if r.metrics and r.metrics.wall_clock_seconds is not None]
        costs = [r.metrics.estimated_cost_usd for r in all_runs_agent
                 if r.metrics and r.metrics.estimated_cost_usd is not None]

        mean_dur = f"{statistics.mean(durations):.1f}s" if durations else "N/A"
        mean_cost = f"${statistics.mean(costs):.4f}" if costs else "N/A"

        lines.append(f"| `{agent_id}` | {len(agent_summaries)} | {overall_rate} | {mean_dur} | {mean_cost} |")

    lines.append("")
    path.write_text("\n".join(lines))
