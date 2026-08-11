from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerTaskState
from mythos.players.context import TaskContext
from mythos.core.followups import ContextScope
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.tasks import TaskCatalog


class TaskRunStatus(StrEnum):
    SUCCESS = "success"


@dataclass(frozen=True, slots=True)
class TaskRun:
    task_id: str
    status: TaskRunStatus
    exception: int

    def body(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "exception": self.exception,
        }


@dataclass(frozen=True, slots=True)
class TaskRunReport:
    runs: tuple[TaskRun, ...]

    def body(self) -> dict[str, object]:
        return {"tasks": [run.body() for run in self.runs]}


class TaskHandlerFailure(RuntimeError):
    """A handler failure that the command layer records after batch rollback."""

    def __init__(self, player_id: UUID, task_id: str) -> None:
        super().__init__(f"Task Handler failed for task {task_id!r}.")
        self.player_id = player_id
        self.task_id = task_id


@dataclass(frozen=True)
class TaskService:
    catalog: TaskCatalog
    pre_commit_interfaces: PlayerInterfaces = PlayerInterfaces.NONE

    def snapshot(self, player: Player) -> dict[str, object]:
        return {"tasks": [state.body() for state in player.tasks.states]}

    def report(self, report: TaskRunReport) -> dict[str, object]:
        return report.body()

    async def run_loaded(
        self,
        session: AsyncSession,
        player: Player,
        scope: ContextScope | None = None,
    ) -> TaskRunReport:
        execution_scope = scope or ContextScope.silent()
        await player.load_interfaces(PlayerInterfaces.TASKS)
        task_ids = player.tasks.execution_snapshot()
        definitions = tuple(self.catalog.task(task_id) for task_id in task_ids)
        interfaces = PlayerInterfaces.TASKS | self.pre_commit_interfaces
        for definition in definitions:
            interfaces |= definition.dependencies
        await player.load_interfaces(interfaces)
        runs: list[TaskRun] = []

        for task_id, definition in zip(task_ids, definitions, strict=True):
            record = player.tasks._record(task_id)
            if record is None:
                runs.append(TaskRun(task_id, TaskRunStatus.SUCCESS, 0))
                continue
            context = TaskContext(
                player=player,
                task_id=task_id,
                time_1=record.time_1,
                time_2=record.time_2,
                exception=record.exception,
                meta=_decode_record_meta(record),
                now=_utcnow(),
                scope=execution_scope,
            )
            try:
                await definition.handler(context)
            except Exception as error:
                raise TaskHandlerFailure(player.id, task_id) from error
            completed_at = _utcnow()
            if player.tasks._is_current_record(record):
                player.tasks.apply_context(record, context, completed_at)
            current = player.tasks._record(task_id)
            runs.append(
                TaskRun(
                    task_id,
                    TaskRunStatus.SUCCESS,
                    current.exception if current is not None else context.exception,
                )
            )

        return TaskRunReport(tuple(runs))

    @staticmethod
    async def record_handler_failure(
        session: AsyncSession,
        player_id: UUID,
        task_id: str,
    ) -> int:
        result = await session.execute(
            update(PlayerTaskState)
            .where(
                PlayerTaskState.player_id == player_id,
                PlayerTaskState.task_id == task_id,
            )
            .values(
                exception=PlayerTaskState.exception + 1,
                updated_at=_utcnow(),
            )
            .returning(PlayerTaskState.exception)
        )
        row = result.one_or_none()
        if row is None:
            raise RuntimeError("Task state disappeared while recording a Handler failure.")
        return row[0]


def _decode_record_meta(record: PlayerTaskState) -> dict[str, object]:
    from mythos.players.interfaces.tasks import decode_task_meta

    return decode_task_meta(record.meta)


def _utcnow() -> datetime:
    return datetime.now(UTC)
