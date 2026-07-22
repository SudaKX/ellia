from __future__ import annotations

from mythos.players.player import Player
from mythos.registry.files import FileRegistry, VirtualFile


class FileAccessDeniedError(Exception):
    pass


class FileService:
    def __init__(self, registry: FileRegistry) -> None:
        self._registry = registry

    def list_files(self, player: Player) -> tuple[VirtualFile, ...]:
        return self._registry.visible(player)

    def read(self, player: Player, stable_id: str) -> VirtualFile:
        file = self._registry.get(stable_id)
        if file.access_rule is not None and not file.access_rule(player):
            raise FileAccessDeniedError
        return file
