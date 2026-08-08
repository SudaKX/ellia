from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from mythos.players.interfaces.accounts import AccountInterface
from mythos.players.interfaces.artifacts import ArtifactInterface
from mythos.players.interfaces.credits import CreditInterface
from mythos.players.interfaces.hints import HintInterface
from mythos.players.interfaces.progress import ProgressInterface
from mythos.players.interfaces.tasks import TaskInterface
from mythos.players.interfaces.versioning import VersionedPlayerInterface
from mythos.players.interface_selection import PlayerInterfaces
from mythos.registry.files.merged_tree import MergedFileTree
from mythos.registry.files.player_tree import PlayerFileTree

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from mythos.players.factory import PlayerFactory


class PlayerInterfaceNotLoadedError(Exception):
    pass


class PlayerInterfaceVersionError(Exception):
    pass


_VERSIONED_INTERFACE_SPECS = (
    (PlayerInterfaces.PROGRESS, "progress"),
    (PlayerInterfaces.ARTIFACTS, "artifacts"),
    (PlayerInterfaces.ACCOUNTS, "accounts"),
    (PlayerInterfaces.CREDITS, "credits"),
    (PlayerInterfaces.HINTS, "hints"),
)


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
        self._tasks: TaskInterface | None = None
        self._file_tree_cache: PlayerFileTree | None = None

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

    @property
    def tasks(self) -> TaskInterface:
        if self._tasks is None:
            raise PlayerInterfaceNotLoadedError("tasks interface not loaded")
        return self._tasks

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
        if PlayerInterfaces.TASKS in interfaces:
            await self.load_tasks()

    async def load_progress(self) -> ProgressInterface:
        if self._progress is None:
            self._progress = await self._factory.load_progress(
                self._session,
                self._player_id,
                writable=self._writable,
                on_mutation=self.invalidate_cache,
            )
        return self._progress

    async def load_artifacts(self) -> ArtifactInterface:
        if self._artifacts is None:
            self._artifacts = await self._factory.load_artifacts(
                self._session,
                self._player_id,
                writable=self._writable,
                on_mutation=self.invalidate_cache,
            )
        return self._artifacts

    async def load_accounts(self) -> AccountInterface:
        if self._accounts is None:
            self._accounts = await self._factory.load_accounts(
                self._session,
                self._player_id,
                writable=self._writable,
                on_mutation=self.invalidate_cache,
            )
        return self._accounts

    async def load_credits(self) -> CreditInterface:
        if self._credits is None:
            self._credits = await self._factory.load_credits(
                self._session,
                self._player_id,
                writable=self._writable,
                on_mutation=self.invalidate_cache,
            )
        return self._credits

    async def load_hints(self) -> HintInterface:
        if self._hints is None:
            self._hints = await self._factory.load_hints(
                self._session,
                self._player_id,
                writable=self._writable,
                on_mutation=self.invalidate_cache,
            )
        return self._hints

    async def load_tasks(self) -> TaskInterface:
        if self._tasks is None:
            self._tasks = await self._factory.load_tasks(
                self._session,
                self._player_id,
                writable=self._writable,
                on_mutation=self.invalidate_cache,
            )
        return self._tasks

    def invalidate_cache(self) -> None:
        self._file_tree_cache = None

    def get_file_tree(self, merged_tree: MergedFileTree, tree_version: str) -> PlayerFileTree:
        if self._file_tree_cache is None:
            self._file_tree_cache = merged_tree.fruit(
                self.artifacts.tree_nodes(),
                tree_version=tree_version,
            )
        return self._file_tree_cache

    def state_versions(self, interfaces: PlayerInterfaces) -> dict[str, int]:
        if not isinstance(interfaces, PlayerInterfaces):
            raise PlayerInterfaceVersionError("Player interface versions require a PlayerInterfaces bitmask.")
        if int(interfaces) & ~int(PlayerInterfaces.ALL):
            raise PlayerInterfaceVersionError("Player interface versions contain unknown interface bits.")

        versions: dict[str, int] = {}
        for interface_flag, interface_name in _VERSIONED_INTERFACE_SPECS:
            if not interfaces & interface_flag:
                continue
            interface = getattr(self, interface_name)
            if not isinstance(interface, VersionedPlayerInterface):
                raise PlayerInterfaceVersionError(
                    f"Player interface {interface_name!r} does not provide a state version."
                )
            version = interface.version
            if isinstance(version, bool) or not isinstance(version, int) or version < 0:
                raise PlayerInterfaceVersionError(
                    f"Player interface {interface_name!r} returned an invalid state version."
                )
            versions[interface_name] = version
        return versions
