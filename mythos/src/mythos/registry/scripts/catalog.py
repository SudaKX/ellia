from __future__ import annotations

from collections.abc import Mapping

from mythos.players.player import Player
from mythos.registry.scripts.definitions import Script


class ScriptCatalog:
    def __init__(self, scripts: Mapping[str, Script]) -> None:
        self._scripts = dict(scripts)

    def visible(self, player: Player) -> tuple[Script, ...]:
        return tuple(script for script in self._scripts.values() if script.access_rule is None or script.access_rule(player))
