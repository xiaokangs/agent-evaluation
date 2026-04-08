"""
Report generation: aggregates runs into a side-by-side comparison.
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from core.schemas import AgentTaskSummary, Report, Run, RunStatus


def build_report(runs: list[Run]) -> Report:
    """Aggregate a flat list of runs into a Report."""

    # Group by (agent_id, task_id)
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

    return Report(
        generated_at=datetime.now(timezone.utc),
        task_ids=sorted({r.task_id for r in runs}),
        agent_ids=sorted({r.agent_id for r in runs}),
        summaries=summaries,
    )


def write_json(report: Report, path: Path) -> None:
    path.write_text(report.model_dump_json(indent=2))


def write_markdown(report: Report, path: Path) -> None:
    lines: list[str] = [
        f"# Agent Evaluation Report",
        f"",
        f"Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"",
        f"Agents: {', '.join(report.agent_ids)}",
        f"Tasks: {', '.join(report.task_ids)}",
        f"",
    ]

    for task_id in report.task_ids:
        lines += [f"## Task: `{task_id}`", ""]
        task_summaries = [s for s in report.summaries if s.task_id == task_id]

        # Header row
        lines.append("| Agent | Runs | Success Rate | Mean Duration | Mean Tokens | Mean Cost |")
        lines.append("|-------|------|-------------|---------------|-------------|-----------|")

        for s in task_summaries:
            sr = f"{s.success_rate:.0%}" if s.success_rate is not None else "N/A"
            dur = f"{s.mean_duration_seconds:.1f}s" if s.mean_duration_seconds is not None else "N/A"
            tok = f"{s.mean_total_tokens:,.0f}" if s.mean_total_tokens is not None else "N/A"
            cost = f"${s.mean_cost_usd:.4f}" if s.mean_cost_usd is not None else "N/A"
            lines.append(f"| {s.agent_id} | {len(s.runs)} | {sr} | {dur} | {tok} | {cost} |")

        lines.append("")

    path.write_text("\n".join(lines))
