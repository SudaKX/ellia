from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerTaskState
from mythos.players.context import TaskContext
from mythos.players.loader import PlayerLoader
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.tasks import TaskCatalog, TaskHandlerError


class TaskRunStatus(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


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


@dataclass(frozen=True)
class TaskService:
    player_loader: PlayerLoader
    catalog: TaskCatalog
    pre_commit_hooks: tuple[object, ...] = ()
    pre_commit_interfaces: PlayerInterfaces = PlayerInterfaces.NONE

    def snapshot(self, player: Player) -> dict[str, object]:
        return {"tasks": [state.body() for state in player.tasks.states]}

    def report(self, report: TaskRunReport) -> dict[str, object]:
        return report.body()

    async def run_itx(self, session: AsyncSession, player_id: UUID) -> TaskRunReport:
        await self.player_loader.lock_player(session, player_id)
        player = await self.player_loader.load_locked(
            session,
            player_id,
            interfaces=PlayerInterfaces.TASKS,
        )
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
            )
            savepoint = await session.begin_nested()
            try:
                await definition.handler(context)
            except TaskHandlerError:
                await savepoint.rollback()
                exception = await self._increment_exception(session, player_id, task_id)
                runs.append(TaskRun(task_id, TaskRunStatus.FAILURE, exception))
                player = await self.player_loader.reload(
                    session,
                    player_id,
                    interfaces=interfaces,
                )
                continue
            except BaseException:
                await savepoint.rollback()
                raise

            try:
                completed_at = _utcnow()
                if player.tasks._is_current_record(record):
                    player.tasks.apply_context(record, context, completed_at)
                for hook in self.pre_commit_hooks:
                    await hook(session, player)  # type: ignore[misc]
                await savepoint.commit()
            except BaseException:
                await savepoint.rollback()
                raise
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
    async def _increment_exception(
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
