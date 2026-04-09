"""
agent-eval CLI entry point.

Usage:
  # Run a single task
  python cli.py run --task datasets/tasks/fix_fibonacci.json --agents claude-code,codex --runs 3

  # Run all tasks in a directory (creates results/<batch-id>/)
  python cli.py batch --agents claude-code,codex --runs 3

  # Generate a report from a batch folder
  python cli.py report --input-dir results/batch_20260408_143000 --output report.md
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from core.schemas import Task

app = typer.Typer(name="agent-eval", help="Side-by-side AI agent evaluation tool")
console = Console()


def _build_adapter_map():
    from agents.claude_code import ClaudeCodeAdapter
    from agents.codex import CodexAdapter
    from agents.langgraph_agent import LangGraphAdapter
    return {
        "claude-code": ClaudeCodeAdapter(),
        "codex": CodexAdapter(),
        "langgraph": LangGraphAdapter(),
    }


def _resolve_agents(agents_str: str) -> list:
    adapter_map = _build_adapter_map()
    selected = [a.strip() for a in agents_str.split(",")]
    for agent_id in selected:
        if agent_id not in adapter_map:
            console.print(f"[red]Unknown agent: {agent_id}. Available: {list(adapter_map)}[/red]")
            raise typer.Exit(1)
    return [adapter_map[a] for a in selected]


@app.command()
def run(
    task: Path = typer.Option(..., help="Path to task JSON file"),
    agents: str = typer.Option(..., help="Comma-separated agent IDs (e.g. claude-code,codex)"),
    runs: int = typer.Option(1, help="Number of repeated runs per agent"),
    output_dir: Path = typer.Option(Path("results"), help="Directory to write run JSON files"),
    keep_workspaces: bool = typer.Option(False, help="Keep isolated workspaces after run"),
) -> None:
    """Execute a single task against one or more agents."""
    from core.run_manager import RunManager
    from evaluators.coding import CodingEvaluator

    task_def = Task(**json.loads(task.read_text()))
    adapters = _resolve_agents(agents)

    manager = RunManager(
        output_dir=output_dir,
        evaluator=CodingEvaluator(),
        keep_workspaces=keep_workspaces,
    )

    all_runs = []
    for adapter in adapters:
        console.print(f"Running [bold]{task_def.id}[/bold] with [bold]{adapter.agent_id}[/bold] ({runs}x)...")
        agent_runs = manager.execute(task_def, adapter, run_count=runs)
        all_runs.extend(agent_runs)
        for r in agent_runs:
            passed = r.validation.passed if r.validation else None
            icon = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            console.print(f"  run {r.run_index}: {icon}  {r.metrics.wall_clock_seconds:.1f}s")

    console.print(f"\n[green]Done. {len(all_runs)} run(s) written to {output_dir}/[/green]")


@app.command()
def batch(
    agents: str = typer.Option(..., help="Comma-separated agent IDs (e.g. claude-code,codex)"),
    runs: int = typer.Option(1, help="Number of repeated runs per agent per task"),
    tasks_dir: Path = typer.Option(Path("datasets/tasks"), help="Directory of task JSON files"),
    output_dir: Path = typer.Option(Path("results"), help="Parent directory for batch output"),
    batch_id: str = typer.Option("", help="Batch ID (default: auto timestamp)"),
    keep_workspaces: bool = typer.Option(False, help="Keep isolated workspaces after run"),
) -> None:
    """Run all tasks in a directory against one or more agents.

    Results are written to output_dir/<batch-id>/ with a manifest.json.
    """
    from core.run_manager import RunManager
    from evaluators.coding import CodingEvaluator
    from core.schemas import Run

    task_files = sorted(tasks_dir.glob("*.json"))
    if not task_files:
        console.print(f"[red]No task files found in {tasks_dir}[/red]")
        raise typer.Exit(1)

    tasks = [Task(**json.loads(f.read_text())) for f in task_files]
    adapters = _resolve_agents(agents)

    if not batch_id:
        batch_id = datetime.now().strftime("batch_%Y%m%d_%H%M%S")

    batch_dir = output_dir / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    console.print(f"Batch [bold]{batch_id}[/bold]")
    console.print(f"  Tasks:  {len(tasks)}")
    console.print(f"  Agents: {[a.agent_id for a in adapters]}")
    console.print(f"  Runs:   {runs} per agent per task")
    console.print(f"  Output: {batch_dir}/\n")

    manager = RunManager(
        output_dir=batch_dir,
        evaluator=CodingEvaluator(),
        keep_workspaces=keep_workspaces,
    )

    started_at = datetime.now(timezone.utc)
    all_runs: list[Run] = []

    for task_def in tasks:
        for adapter in adapters:
            console.print(f"[bold]{task_def.id}[/bold] / {adapter.agent_id} ({runs}x) ...", end="  ")
            agent_runs = manager.execute(task_def, adapter, run_count=runs)
            all_runs.extend(agent_runs)
            passed = sum(1 for r in agent_runs if r.validation and r.validation.passed)
            console.print(f"[green]{passed}/{runs} PASS[/green]" if passed == runs
                          else f"[yellow]{passed}/{runs} PASS[/yellow]")

    ended_at = datetime.now(timezone.utc)

    # Write manifest
    manifest = {
        "batch_id": batch_id,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
        "duration_seconds": (ended_at - started_at).total_seconds(),
        "agents": [a.agent_id for a in adapters],
        "task_ids": [t.id for t in tasks],
        "runs_per_agent_per_task": runs,
        "total_runs": len(all_runs),
        "passed": sum(1 for r in all_runs if r.validation and r.validation.passed),
        "failed": sum(1 for r in all_runs if r.validation and not r.validation.passed),
    }
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    total_pass = manifest["passed"]
    total_fail = manifest["failed"]
    console.print(f"\n[green]Batch complete.[/green] {total_pass} passed, {total_fail} failed.")
    console.print(f"Results: {batch_dir}/")
    console.print(f"Report:  python cli.py report --input-dir {batch_dir} --output report.md")


@app.command()
def report(
    input_dir: Path = typer.Option(..., help="Batch directory (contains run JSON files)"),
    output: Path = typer.Option(Path("report.md"), help="Output file (.md or .json)"),
) -> None:
    """Generate a side-by-side comparison report from a batch directory."""
    from core.schemas import Run
    from core.report import build_report, write_json, write_markdown

    # Load manifest if present
    manifest_path = input_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    run_files = [f for f in input_dir.glob("*.json") if f.name != "manifest.json"]
    if not run_files:
        console.print(f"[red]No run files found in {input_dir}[/red]")
        raise typer.Exit(1)

    all_runs = [Run(**json.loads(f.read_text())) for f in run_files]
    rpt = build_report(all_runs, manifest=manifest)

    if output.suffix == ".json":
        write_json(rpt, output)
    else:
        write_markdown(rpt, output)

    console.print(f"[green]Report written to {output}[/green]")


if __name__ == "__main__":
    app()
