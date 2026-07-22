from __future__ import annotations

from mythos.players.player import Player
from mythos.registry.scripts import ScriptRegistry


class ScriptService:
    def __init__(self, registry: ScriptRegistry) -> None:
        self._registry = registry

    def visible(self, player: Player) -> tuple[dict[str, object], ...]:
        return tuple({"stable_id": item.stable_id, "revision": item.revision, "body": dict(item.body)} for item in self._registry.visible(player))
