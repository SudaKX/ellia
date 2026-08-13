from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeAlias

if TYPE_CHECKING:
    from mythos.players.player import Player

ScriptAccessRule: TypeAlias = Callable[["Player"], bool]


@dataclass(frozen=True)
class Script:
    stable_id: str
    revision: str
    body: Mapping[str, Any]
    access_rule: ScriptAccessRule | None = None
