"""
agent-eval CLI entry point.

Usage:
  python cli.py run --task datasets/tasks/example_fix_bug.json --agents claude-code,codex --runs 3
  python cli.py report --input-dir results/ --output report.md
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console

from core.schemas import Task

app = typer.Typer(name="agent-eval", help="Side-by-side AI agent evaluation tool")
console = Console()


@app.command()
def run(
    task: Path = typer.Option(..., help="Path to task JSON file"),
    agents: str = typer.Option(..., help="Comma-separated agent IDs (e.g. claude-code,codex)"),
    runs: int = typer.Option(1, help="Number of repeated runs per agent"),
    output_dir: Path = typer.Option(Path("results"), help="Directory to write run JSON files"),
    keep_workspaces: bool = typer.Option(False, help="Keep isolated workspaces after run"),
) -> None:
    """Execute a task against one or more agents."""
    from core.run_manager import RunManager
    from evaluators.coding import CodingEvaluator
    from agents.claude_code import ClaudeCodeAdapter
    from agents.codex import CodexAdapter

    task_def = Task(**json.loads(task.read_text()))

    adapter_map = {
        "claude-code": ClaudeCodeAdapter(),
        "codex": CodexAdapter(),
    }

    selected_agents = [a.strip() for a in agents.split(",")]
    for agent_id in selected_agents:
        if agent_id not in adapter_map:
            console.print(f"[red]Unknown agent: {agent_id}. Available: {list(adapter_map)}[/red]")
            raise typer.Exit(1)

    manager = RunManager(
        output_dir=output_dir,
        evaluator=CodingEvaluator(),
        keep_workspaces=keep_workspaces,
    )

    all_runs = []
    for agent_id in selected_agents:
        console.print(f"Running task [bold]{task_def.id}[/bold] with agent [bold]{agent_id}[/bold] ({runs}x)...")
        agent_runs = manager.execute(task_def, adapter_map[agent_id], run_count=runs)
        all_runs.extend(agent_runs)
        for r in agent_runs:
            status = r.validation.passed if r.validation else "?"
            console.print(f"  run {r.run_index}: {'PASS' if status else 'FAIL'} ({r.metrics})")

    console.print(f"\n[green]Done. {len(all_runs)} run(s) written to {output_dir}/[/green]")


@app.command()
def report(
    input_dir: Path = typer.Option(Path("results"), help="Directory of run JSON files"),
    output: Path = typer.Option(Path("report.md"), help="Output file (.md or .json)"),
) -> None:
    """Generate a comparison report from run results."""
    from core.schemas import Run
    from core.report import build_report, write_json, write_markdown

    run_files = list(input_dir.glob("*.json"))
    if not run_files:
        console.print(f"[red]No run files found in {input_dir}[/red]")
        raise typer.Exit(1)

    all_runs = [Run(**json.loads(f.read_text())) for f in run_files]
    rpt = build_report(all_runs)

    if output.suffix == ".json":
        write_json(rpt, output)
    else:
        write_markdown(rpt, output)

    console.print(f"[green]Report written to {output}[/green]")


if __name__ == "__main__":
    app()
