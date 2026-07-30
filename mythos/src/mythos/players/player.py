from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from mythos.players.interfaces.artifacts import ArtifactInterface
from mythos.players.interfaces.progress import ProgressInterface

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from mythos.players.factory import PlayerFactory


class PlayerInterfaceNotLoadedError(Exception):
    pass


class Player:
    def __init__(
        self,
        player_id: UUID,
        session: AsyncSession,
        factory: PlayerFactory,
        *,
        writable: bool,
    ) -> None:
        self._player_id = player_id
        self._session = session
        self._factory = factory
        self._writable = writable
        self._progress: ProgressInterface | None = None
        self._artifacts: ArtifactInterface | None = None

    @property
    def id(self) -> UUID:
        return self._player_id

    @property
    def progress(self) -> ProgressInterface:
        if self._progress is None:
            raise PlayerInterfaceNotLoadedError("progress interface not loaded")
        return self._progress

    @property
    def artifacts(self) -> ArtifactInterface:
        if self._artifacts is None:
            raise PlayerInterfaceNotLoadedError("artifacts interface not loaded")
        return self._artifacts

    async def load_progress(self) -> ProgressInterface:
        if self._progress is None:
            self._progress = await self._factory.load_progress(
                self._session, self._player_id, writable=self._writable
            )
        return self._progress

    async def load_artifacts(self) -> ArtifactInterface:
        if self._artifacts is None:
            self._artifacts = await self._factory.load_artifacts(
                self._session, self._player_id, writable=self._writable
            )
        return self._artifacts
