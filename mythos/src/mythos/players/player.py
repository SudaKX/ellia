from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from mythos.players.interfaces.accounts import AccountInterface
from mythos.players.interfaces.artifacts import ArtifactInterface
from mythos.players.interfaces.credits import CreditInterface
from mythos.players.interfaces.hints import HintInterface
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.interface_selection import PlayerInterfaces

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
        self._accounts: AccountInterface | None = None
        self._credits: CreditInterface | None = None
        self._hints: HintInterface | None = None

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

    @property
    def accounts(self) -> AccountInterface:
        if self._accounts is None:
            raise PlayerInterfaceNotLoadedError("accounts interface not loaded")
        return self._accounts

    @property
    def credits(self) -> CreditInterface:
        if self._credits is None:
            raise PlayerInterfaceNotLoadedError("credits interface not loaded")
        return self._credits

    @property
    def hints(self) -> HintInterface:
        if self._hints is None:
            raise PlayerInterfaceNotLoadedError("hints interface not loaded")
        return self._hints

    async def load_interfaces(
        self,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
    ) -> None:
        if PlayerInterfaces.PROGRESS in interfaces:
            await self.load_progress()
        if PlayerInterfaces.ARTIFACTS in interfaces:
            await self.load_artifacts()
        if PlayerInterfaces.ACCOUNTS in interfaces:
            await self.load_accounts()
        if PlayerInterfaces.CREDITS in interfaces:
            await self.load_credits()
        if PlayerInterfaces.HINTS in interfaces:
            await self.load_hints()

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

    async def load_accounts(self) -> AccountInterface:
        if self._accounts is None:
            self._accounts = await self._factory.load_accounts(
                self._session,
                self._player_id,
                writable=self._writable,
            )
        return self._accounts

    async def load_credits(self) -> CreditInterface:
        if self._credits is None:
            self._credits = await self._factory.load_credits(
                self._session,
                self._player_id,
                writable=self._writable,
            )
        return self._credits

    async def load_hints(self) -> HintInterface:
        if self._hints is None:
            self._hints = await self._factory.load_hints(
                self._session,
                self._player_id,
                writable=self._writable,
            )
        return self._hints
