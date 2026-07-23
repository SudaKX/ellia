from __future__ import annotations

from collections.abc import Mapping

from mythos.players.player import Player
from mythos.registry.errors import RegistryError
from mythos.registry.files.definitions import VirtualFile


class FileCatalog:
    def __init__(self, files: Mapping[str, VirtualFile]) -> None:
        self._files = dict(files)

    def get(self, stable_id: str) -> VirtualFile:
        try:
            return self._files[stable_id]
        except KeyError as error:
            raise RegistryError("Virtual file not found.") from error

    def visible(self, player: Player) -> tuple[VirtualFile, ...]:
        return tuple(file for file in self._files.values() if file.access_rule is None or file.access_rule(player))
