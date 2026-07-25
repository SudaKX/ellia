from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerProgress
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.player import Player
from mythos.registry.bundle import RuntimeCatalogs


class PlayerNotFoundError(Exception):
    pass


class PlayerFactory:
    def __init__(self, catalogs: RuntimeCatalogs) -> None:
        self._catalogs = catalogs

    async def load(self, session: AsyncSession, player_id: UUID, *, writable: bool) -> Player:
        progress = await session.get(PlayerProgress, player_id)
        if progress is None:
            raise PlayerNotFoundError
        return Player(
            id=player_id,
            progress=ProgressInterface(progress, writable=writable, catalogs=self._catalogs),
        )
