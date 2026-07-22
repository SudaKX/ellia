from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from mythos.players.player import Player
from mythos.registry.modules import DuplicateStableIdError, RegistryError, RegistryFrozenError

ScriptAccessRule = Callable[[Player], bool]


@dataclass(frozen=True)
class Script:
    stable_id: str
    revision: str
    body: Mapping[str, Any]
    access_rule: ScriptAccessRule | None = None


class ScriptRegistry:
    def __init__(self) -> None:
        self._scripts: dict[str, Script] = {}
        self._frozen = False

    def register(self, script: Script) -> None:
        if self._frozen:
            raise RegistryFrozenError("The script registry is frozen.")
        if not script.stable_id:
            raise RegistryError("Scripts require a stable ID.")
        if script.stable_id in self._scripts:
            raise DuplicateStableIdError(script.stable_id)
        self._scripts[script.stable_id] = script

    def freeze(self) -> None:
        self._frozen = True

    def visible(self, player: Player) -> tuple[Script, ...]:
        if not self._frozen:
            raise RegistryError("The script registry must be frozen before use.")
        return tuple(script for script in self._scripts.values() if script.access_rule is None or script.access_rule(player))
