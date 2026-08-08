from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerRecord, PlayerTaskState
from mythos.players.context import TaskContext
from mythos.players.factory import PlayerFactory, PlayerNotFoundError
from mythos.players.interface_selection import PlayerInterfaces
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


class TaskExecutor:
    def __init__(
        self,
        player_factory: PlayerFactory,
        catalog: TaskCatalog,
        pre_commit_hooks: tuple[object, ...] = (),
        pre_commit_interfaces: PlayerInterfaces = PlayerInterfaces.NONE,
    ) -> None:
        self._player_factory = player_factory
        self._catalog = catalog
        self._pre_commit_hooks = pre_commit_hooks
        self._pre_commit_interfaces = pre_commit_interfaces

    async def run_itx(self, session: AsyncSession, player_id: UUID) -> TaskRunReport:
        await self._lock_player(session, player_id)
        task_ids = tuple(
            (
                await session.scalars(
                    select(PlayerTaskState.task_id)
                    .where(PlayerTaskState.player_id == player_id)
                    .order_by(PlayerTaskState.task_id)
                )
            ).all()
        )
        definitions = tuple(self._catalog.task(task_id) for task_id in task_ids)
        interfaces = PlayerInterfaces.TASKS | self._pre_commit_interfaces
        for definition in definitions:
            interfaces |= definition.dependencies
        player = await self._load_player(session, player_id, interfaces)
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
                player = await self._load_player(session, player_id, interfaces)
                continue
            except BaseException:
                await savepoint.rollback()
                raise

            try:
                completed_at = _utcnow()
                if player.tasks._is_current_record(record):
                    player.tasks.apply_context(record, context, completed_at)
                for hook in self._pre_commit_hooks:
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

    async def _load_player(
        self,
        session: AsyncSession,
        player_id: UUID,
        interfaces: PlayerInterfaces,
    ) -> Player:
        player = await self._player_factory.create(session, player_id, writable=True)
        await player.load_interfaces(interfaces)
        return player

    @staticmethod
    async def _lock_player(session: AsyncSession, player_id: UUID) -> None:
        result = await session.execute(
            update(PlayerRecord)
            .where(PlayerRecord.id == player_id)
            .values(last_accessed_at=PlayerRecord.last_accessed_at)
        )
        if result.rowcount != 1:
            raise PlayerNotFoundError

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
