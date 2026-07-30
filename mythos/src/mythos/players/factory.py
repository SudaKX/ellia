from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from mythos.core.file_ids import FileIdCodec
from mythos.persistence.models import PlayerArtifact, PlayerProgress, PlayerProgressCheckpoint
from mythos.players.interfaces.artifacts import ArtifactInterface
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.player import Player
from mythos.registry.bundle import RuntimeCatalogs
from mythos.services.object_store.service import ObjectStore


class PlayerNotFoundError(Exception):
    pass


class PlayerFactory:
    def __init__(
        self,
        catalogs: RuntimeCatalogs,
        object_store: ObjectStore,
        file_ids: FileIdCodec,
    ) -> None:
        self._catalogs = catalogs
        self._object_store = object_store
        self._file_ids = file_ids

    async def load(self, session: AsyncSession, player_id: UUID, *, writable: bool) -> Player:
        progress = await session.scalar(
            select(PlayerProgress)
            .where(PlayerProgress.player_id == player_id)
            .options(
                selectinload(PlayerProgress.unlocked_nodes),
                selectinload(PlayerProgress.frontier_nodes),
            )
        )
        if progress is None:
            raise PlayerNotFoundError
        checkpoint = None
        if progress.current_checkpoint_sequence >= 0:
            checkpoint = await session.get(
                PlayerProgressCheckpoint,
                (player_id, progress.current_checkpoint_sequence),
            )
        return Player(
            id=player_id,
            progress=ProgressInterface(
                progress,
                writable=writable,
                catalogs=self._catalogs,
                checkpoint=checkpoint,
            ),
            artifacts=await ArtifactInterface.load(
                session,
                player_id,
                self._catalogs.artifacts,
                self._object_store,
                self._file_ids,
                writable=writable,
            ),
        )
