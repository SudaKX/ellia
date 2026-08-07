from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mythos.core.commands.executor import CommandTransactionExecutor
from mythos.persistence.models.artifacts import PlayerArtifact, PlayerArtifactNode, PlayerArtifactState
from mythos.registry.artifacts.catalog import ArtifactCatalog
from mythos.registry.catalog_snapshots import (
    TemplateSnapshot,
    template_snapshot_changed_keys,
)
from mythos.services.template_snapshots import TemplateSnapshotStore


class ArtifactReconciliationRunner:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        command_executor: CommandTransactionExecutor,
        catalog: ArtifactCatalog,
        snapshot_store: TemplateSnapshotStore,
        *,
        allow_missing_tables: bool = False,
    ) -> None:
        self._session_factory = session_factory
        self._command_executor = command_executor
        self._catalog = catalog
        self._snapshot_store = snapshot_store
        self._allow_missing_tables = allow_missing_tables

    async def run(self) -> None:
        current = self._catalog.snapshot()
        previous = await self._snapshot_store.read()
        requires_baseline = await self._requires_full_reconciliation()
        if (
            not requires_baseline
            and previous is not None
            and previous.template_version == current.template_version
        ):
            return
        player_ids = (
            await self._all_player_ids()
            if requires_baseline or previous is None
            else await self._affected_player_ids(previous, current)
        )
        for player_id in player_ids:
            async with self._session_factory() as session:
                await self._command_executor.execute_nocache(
                    session,
                    player_id,
                    lambda player: player.artifacts.refresh_stale(player),
                    run_pre_commit_hooks=False,
                )
        await self._snapshot_store.write(current)

    async def _requires_full_reconciliation(self) -> bool:
        state_statement = (
            select(PlayerArtifact.player_id)
            .outerjoin(PlayerArtifactState, PlayerArtifactState.player_id == PlayerArtifact.player_id)
            .where(PlayerArtifactState.player_id.is_(None))
            .limit(1)
        )
        try:
            async with self._session_factory() as session:
                if await session.scalar(state_statement) is not None:
                    return True
                node_rows = (
                    await session.execute(
                        select(
                            PlayerArtifactNode.player_id,
                            PlayerArtifactNode.node_id,
                            PlayerArtifactNode.path,
                        )
                    )
                ).all()
                return any(
                    (template := self._catalog.node_template_or_none(node_id)) is None
                    or path != template.path
                    for _, node_id, path in node_rows
                )
        except OperationalError as error:
            if not self._allow_missing_tables or "no such table" not in str(error).lower():
                raise
            return False

    async def _affected_player_ids(
        self,
        previous: TemplateSnapshot | None,
        current: TemplateSnapshot,
    ) -> tuple[UUID, ...]:
        if previous is None:
            return await self._all_player_ids()

        changed_keys = template_snapshot_changed_keys(previous, current)
        current_entries = {(entry.kind, entry.template_id): entry for entry in current.entries}
        artifact_ids = {
            template_id
            for kind, template_id in changed_keys
            if kind == "artifact"
        }
        node_ids = {
            template_id
            for kind, template_id in changed_keys
            if kind == "artifact_node"
        }
        owner_artifact_ids = {
            entry.definition["artifact_locator"]
            for kind, template_id in changed_keys
            if kind == "artifact_node"
            for entry in (current_entries.get((kind, template_id)),)
            if entry is not None and isinstance(entry.definition.get("artifact_locator"), str)
        }
        async with self._session_factory() as session:
            player_ids: set[UUID] = set()
            player_ids.update(await _player_ids_for_artifacts(session, artifact_ids))
            player_ids.update(await _player_ids_for_nodes(session, node_ids))
            player_ids.update(await _player_ids_for_artifacts(session, owner_artifact_ids))
            return tuple(player_ids)

    async def _all_player_ids(self) -> tuple[UUID, ...]:
        try:
            async with self._session_factory() as session:
                player_ids = set(await _player_ids_for_artifacts(session, None))
                player_ids.update(await _player_ids_for_nodes(session, None))
                return tuple(player_ids)
        except OperationalError as error:
            if not self._allow_missing_tables or "no such table" not in str(error).lower():
                raise
            return ()


async def _player_ids_for_artifacts(
    session: AsyncSession,
    artifact_ids: set[str] | None,
) -> tuple[UUID, ...]:
    statement = select(PlayerArtifact.player_id).distinct()
    if artifact_ids is not None:
        if not artifact_ids:
            return ()
        statement = statement.where(PlayerArtifact.artifact_id.in_(artifact_ids))
    return tuple((await session.scalars(statement)).all())


async def _player_ids_for_nodes(
    session: AsyncSession,
    node_ids: set[str] | None,
) -> tuple[UUID, ...]:
    statement = select(PlayerArtifactNode.player_id).distinct()
    if node_ids is not None:
        if not node_ids:
            return ()
        statement = statement.where(PlayerArtifactNode.node_id.in_(node_ids))
    return tuple((await session.scalars(statement)).all())
