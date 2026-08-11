from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mythos.persistence.models import PlayerTaskState
from mythos.players.loader import PlayerLoader
from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.tasks import TaskCatalog
from mythos.services.tasks.snapshot import TaskSnapshotStore


class TaskCatalogEmptyError(RuntimeError):
    pass


class TaskReconciliationRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        player_loader: PlayerLoader,
        catalog: TaskCatalog,
        snapshot_store: TaskSnapshotStore,
        *,
        allow_missing_tables: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._player_loader = player_loader
        self._catalog = catalog
        self._snapshot_store = snapshot_store
        self._allow_missing_tables = allow_missing_tables

    async def run(self) -> None:
        current = self._catalog.snapshot()
        previous = await self._snapshot_store.read()
        sql_task_ids = await self._sql_task_ids()
        catalog_ids = self._catalog.task_ids
        if sql_task_ids and not catalog_ids:
            raise TaskCatalogEmptyError("Task catalog is empty while player tasks exist.")

        stale_ids = sql_task_ids - catalog_ids
        if stale_ids:
            async with self._session_factory() as session:
                async with session.begin():
                    for player_id in await self._player_ids_for_tasks(session, stale_ids):
                        await self._remove_stale_tasks(session, player_id, stale_ids)

        if previous is None or previous.registry_version != current.registry_version:
            await self._snapshot_store.write(current)

    async def _sql_task_ids(self) -> frozenset[str]:
        try:
            async with self._session_factory() as session:
                return frozenset(
                    (
                        await session.scalars(
                            select(PlayerTaskState.task_id).distinct()
                        )
                    ).all()
                )
        except OperationalError as error:
            if not self._allow_missing_tables or "no such table" not in str(error).lower():
                raise
            return frozenset()

    async def _player_ids_for_tasks(
        self,
        session: AsyncSession,
        task_ids: Iterable[str],
    ) -> tuple[UUID, ...]:
        task_ids = tuple(task_ids)
        if not task_ids:
            return ()
        return tuple(
            (
                await session.scalars(
                    select(PlayerTaskState.player_id)
                    .where(PlayerTaskState.task_id.in_(task_ids))
                    .distinct()
                )
            ).all()
        )

    async def _remove_stale_tasks(
        self,
        session: AsyncSession,
        player_id: UUID,
        task_ids: Iterable[str],
    ) -> None:
        player = await self._player_loader.load_writable(
            session,
            player_id,
            interfaces=PlayerInterfaces.TASKS,
        )
        await player.tasks.remove_tasks(task_ids)
