"""Abstract evaluator interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import Run, Task


class Evaluator(ABC):

    @abstractmethod
    def evaluate(self, run: Run, task: Task) -> Run:
        """
        Set run.validation based on the run's workspace/artifacts and return the run.
        (Trace-derived metrics are not an evaluator responsibility yet — P1.)
        """
