from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mythos.players.player import Player
from mythos.registry.modules import DuplicateStableIdError, RegistryError, RegistryFrozenError

FileAccessRule = Callable[[Player], bool]


@dataclass(frozen=True)
class VirtualFile:
    stable_id: str
    path: str
    revision: str
    content: bytes
    media_type: str = "text/plain"
    access_rule: FileAccessRule | None = None


class FileRegistry:
    def __init__(self) -> None:
        self._by_id: dict[str, VirtualFile] = {}
        self._paths: set[str] = set()
        self._frozen = False

    def register(self, file: VirtualFile) -> None:
        if self._frozen:
            raise RegistryFrozenError("The file registry is frozen.")
        if not file.stable_id or not file.path.startswith("/"):
            raise RegistryError("Files require a stable ID and an absolute virtual path.")
        if file.stable_id in self._by_id or file.path in self._paths:
            raise DuplicateStableIdError(file.stable_id)
        self._by_id[file.stable_id] = file
        self._paths.add(file.path)

    def freeze(self) -> None:
        self._frozen = True

    def get(self, stable_id: str) -> VirtualFile:
        if not self._frozen:
            raise RegistryError("The file registry must be frozen before use.")
        try:
            return self._by_id[stable_id]
        except KeyError as error:
            raise RegistryError("Virtual file not found.") from error

    def visible(self, player: Player) -> tuple[VirtualFile, ...]:
        if not self._frozen:
            raise RegistryError("The file registry must be frozen before use.")
        return tuple(file for file in self._by_id.values() if file.access_rule is None or file.access_rule(player))
