from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mythos.core.commands.executor import CommandTransactionExecutor
from mythos.persistence.models.accounts import PlayerVirtualAccount
from mythos.registry.accounts.catalog import VirtualAccountCatalog
from mythos.registry.catalog_snapshots import template_snapshot_changed_keys
from mythos.services.accounts.snapshot import VirtualAccountTemplateSnapshotStore


class AccountCatalogEmptyError(RuntimeError):
    pass


class AccountReconciliationRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        command_executor: CommandTransactionExecutor,
        catalog: VirtualAccountCatalog,
        snapshot_store: VirtualAccountTemplateSnapshotStore,
        *,
        allow_empty_catalog: bool = False,
        allow_missing_tables: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._command_executor = command_executor
        self._catalog = catalog
        self._snapshot_store = snapshot_store
        self._allow_empty_catalog = allow_empty_catalog
        self._allow_missing_tables = allow_missing_tables

    async def run(self) -> None:
        current = self._catalog.snapshot()
        previous = await self._snapshot_store.read()
        changed = previous is None or bool(template_snapshot_changed_keys(previous, current))
        sql_account_ids = await self._sql_account_ids()
        catalog_ids = self._catalog.template_ids
        if sql_account_ids and not catalog_ids and not self._allow_empty_catalog:
            raise AccountCatalogEmptyError("Virtual account catalog is empty while player accounts exist.")
        stale_ids = sql_account_ids - catalog_ids
        if stale_ids:
            for player_id in await self._player_ids_for_accounts(stale_ids):
                async with self._session_factory() as session:
                    await self._command_executor.execute_nocache(
                        session,
                        player_id,
                        lambda player: player.accounts.remove_unregistered(stale_ids),
                        run_pre_commit_hooks=False,
                    )
        if changed:
            await self._snapshot_store.write(current)

    async def _sql_account_ids(self) -> frozenset[str]:
        try:
            async with self._session_factory() as session:
                return frozenset(
                    (await session.scalars(select(PlayerVirtualAccount.account_id).distinct())).all()
                )
        except OperationalError as error:
            if not self._allow_missing_tables or "no such table" not in str(error).lower():
                raise
            return frozenset()

    async def _player_ids_for_accounts(self, account_ids: frozenset[str]) -> tuple[UUID, ...]:
        if not account_ids:
            return ()
        async with self._session_factory() as session:
            return tuple(
                (
                    await session.scalars(
                        select(PlayerVirtualAccount.player_id)
                        .where(PlayerVirtualAccount.account_id.in_(account_ids))
                        .distinct()
                    )
                ).all()
            )
