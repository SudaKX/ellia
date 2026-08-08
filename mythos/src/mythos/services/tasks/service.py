from __future__ import annotations

from dataclasses import dataclass

from mythos.players.player import Player
from mythos.registry.tasks import TaskCatalog
from mythos.services.tasks.executor import TaskExecutor, TaskRunReport


@dataclass(frozen=True)
class TaskService:
    catalog: TaskCatalog
    executor: TaskExecutor

    def snapshot(self, player: Player) -> dict[str, object]:
        return {"tasks": [state.body() for state in player.tasks.states]}

    def report(self, report: TaskRunReport) -> dict[str, object]:
        return report.body()
