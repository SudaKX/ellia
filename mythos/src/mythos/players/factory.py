from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.models import PlayerProgress
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.player import Player


class PlayerNotFoundError(Exception):
    pass


class PlayerFactory:
    @staticmethod
    async def load(session: AsyncSession, player_id: UUID, *, writable: bool) -> Player:
        progress = await session.get(PlayerProgress, player_id)
        if progress is None:
            raise PlayerNotFoundError
        return Player(
            id=player_id,
            progress=ProgressInterface(progress, writable=writable),
        )
