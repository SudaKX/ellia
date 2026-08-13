from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mythos.persistence.models.credits import PlayerCreditBalance
from mythos.players.loader import PlayerLoader
from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.catalog_snapshots import template_snapshot_changed_keys
from mythos.registry.credits import CreditCatalog
from mythos.services.credits.snapshot import CreditTemplateSnapshotStore


class CreditReconciliationRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        player_loader: PlayerLoader,
        catalog: CreditCatalog,
        snapshot_store: CreditTemplateSnapshotStore,
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
        changed = previous is None or bool(template_snapshot_changed_keys(previous, current))
        sql_credit_ids = await self._sql_credit_ids()
        stale_ids = sql_credit_ids - self._catalog.credit_ids
        if stale_ids:
            for player_id in await self._player_ids_for_credits(stale_ids):
                async with self._session_factory() as session:
                    async with session.begin():
                        player = await self._player_loader.load_writable(
                            session,
                            player_id,
                            interfaces=PlayerInterfaces.ALL,
                        )
                        await player.credits.remove_unregistered(stale_ids)
        if changed:
            await self._snapshot_store.write(current)

    async def _sql_credit_ids(self) -> frozenset[str]:
        try:
            async with self._session_factory() as session:
                return frozenset(
                    (await session.scalars(select(PlayerCreditBalance.credit_id).distinct())).all()
                )
        except OperationalError as error:
            if not self._allow_missing_tables or "no such table" not in str(error).lower():
                raise
            return frozenset()

    async def _player_ids_for_credits(self, credit_ids: frozenset[str]) -> tuple[UUID, ...]:
        if not credit_ids:
            return ()
        async with self._session_factory() as session:
            return tuple(
                (
                    await session.scalars(
                        select(PlayerCreditBalance.player_id)
                        .where(PlayerCreditBalance.credit_id.in_(credit_ids))
                        .distinct()
                    )
                ).all()
            )
