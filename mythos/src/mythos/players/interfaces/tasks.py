from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerTaskState
from mythos.registry.tasks import TaskCatalog

if TYPE_CHECKING:
    from mythos.players.context import TaskContext

MAX_TASK_META_BYTES = 64 * 1024


class ReadOnlyTaskError(Exception):
    pass


class TaskMetaError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TaskStateSnapshot:
    task_id: str
    time_1: datetime | None
    time_2: datetime | None
    exception: int
    meta: Mapping[str, object]

    def body(self) -> dict[str, object]:
        return {
            "task_id": self.task_id,
            "time_1": self.time_1.isoformat() if self.time_1 is not None else None,
            "time_2": self.time_2.isoformat() if self.time_2 is not None else None,
            "exception": self.exception,
            "meta": dict(self.meta),
        }


def decode_task_meta(value: str) -> dict[str, object]:
    if not isinstance(value, str):
        raise TaskMetaError("Task meta must be stored as a JSON string.")
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise TaskMetaError("Task meta is not valid JSON.") from error
    if not isinstance(decoded, dict):
        raise TaskMetaError("Task meta must be a JSON object.")
    return decoded


def encode_task_meta(value: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            dict(value),
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as error:
        raise TaskMetaError("Task meta must be JSON serializable.") from error
    if len(encoded.encode("utf-8")) > MAX_TASK_META_BYTES:
        raise TaskMetaError("Task meta exceeds the maximum size.")
    return encoded


class TaskInterface:
    def __init__(
        self,
        player_id: UUID,
        catalog: TaskCatalog,
        session: AsyncSession,
        records: Iterable[PlayerTaskState],
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> None:
        self._player_id = player_id
        self._catalog = catalog
        self._session = session
        self._writable = writable
        self._on_mutation = on_mutation or (lambda: None)
        self._records_by_task_id = {record.task_id: record for record in records}

    @property
    def task_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._records_by_task_id))

    @property
    def states(self) -> tuple[TaskStateSnapshot, ...]:
        return tuple(self._snapshot(record) for record in self._records_by_task_id.values())

    def state(self, task_id: str) -> TaskStateSnapshot | None:
        record = self._records_by_task_id.get(task_id)
        return self._snapshot(record) if record is not None else None

    def _record(self, task_id: str) -> PlayerTaskState | None:
        return self._records_by_task_id.get(task_id)

    def _records(self) -> tuple[PlayerTaskState, ...]:
        return tuple(self._records_by_task_id[task_id] for task_id in self.task_ids)

    def _is_current_record(self, record: PlayerTaskState) -> bool:
        return self._records_by_task_id.get(record.task_id) is record

    async def add_task(self, task_id: str) -> bool:
        self._ensure_writable()
        self._catalog.task(task_id)
        if task_id in self._records_by_task_id:
            return False
        record = PlayerTaskState(
            player_id=self._player_id,
            task_id=task_id,
            exception=0,
            meta=encode_task_meta({}),
        )
        self._session.add(record)
        self._records_by_task_id[task_id] = record
        self._on_mutation()
        return True

    async def remove_task(self, task_id: str) -> bool:
        self._ensure_writable()
        record = self._records_by_task_id.get(task_id)
        if record is None:
            return False
        if inspect(record).pending:
            self._session.expunge(record)
        else:
            await self._session.delete(record)
        self._records_by_task_id.pop(task_id, None)
        self._on_mutation()
        return True

    async def remove_tasks(self, task_ids: Iterable[str]) -> int:
        self._ensure_writable()
        removed = 0
        for task_id in tuple(task_ids):
            if await self.remove_task(task_id):
                removed += 1
        return removed

    def apply_context(
        self,
        record: PlayerTaskState,
        context: TaskContext,
        completed_at: datetime,
    ) -> bool:
        if not self._is_current_record(record):
            return False
        if not context.deferred:
            record.time_1 = completed_at
        record.time_2 = context.extra_time
        record.meta = encode_task_meta(context._meta_value())
        record.updated_at = completed_at
        self._on_mutation()
        return True

    def _snapshot(self, record: PlayerTaskState | None) -> TaskStateSnapshot | None:
        if record is None:
            return None
        return TaskStateSnapshot(
            task_id=record.task_id,
            time_1=record.time_1,
            time_2=record.time_2,
            exception=record.exception,
            meta=decode_task_meta(record.meta),
        )

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyTaskError("Read-only players cannot modify tasks.")
