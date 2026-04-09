"""
Run manager: orchestrates task execution across agents and run counts.

Flow per (task, agent, run_index):
  1. prepare_workspace
  2. adapter.run()
  3. evaluator.evaluate()   ← must happen before cleanup
  4. cleanup_workspace
  5. persist run result as JSON
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.schemas import Run, Task
from core.workspace import isolated_workspace
from agents.base import AgentAdapter
from evaluators.base import Evaluator


class RunManager:

    def __init__(
        self,
        output_dir: Path,
        evaluator: Evaluator,
        keep_workspaces: bool = False,
    ) -> None:
        self.output_dir = output_dir
        self.evaluator = evaluator
        self.keep_workspaces = keep_workspaces
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def execute(
        self,
        task: Task,
        adapter: AgentAdapter,
        run_count: int = 1,
    ) -> list[Run]:
        results: list[Run] = []
        for i in range(run_count):
            run = self._execute_one(task, adapter, run_index=i)
            self._persist(run)
            results.append(run)
        return results

    def _execute_one(self, task: Task, adapter: AgentAdapter, run_index: int) -> Run:
        with isolated_workspace(task, keep=self.keep_workspaces) as workspace:
            run = adapter.run(task, str(workspace), run_index)
            run = self.evaluator.evaluate(run, task)
        return run

    def _persist(self, run: Run) -> None:
        path = self.output_dir / f"{run.task_id}__{run.agent_id}__{run.run_id}.json"
        path.write_text(run.model_dump_json(indent=2))
