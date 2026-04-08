"""Abstract evaluator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import Run, Task


class Evaluator(ABC):

    @abstractmethod
    def evaluate(self, run: Run, task: Task) -> Run:
        """
        Populate run.validation and refine run.metrics based on run artifacts.
        Must return the (possibly modified) run.
        """
