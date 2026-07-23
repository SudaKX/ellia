from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from mythos.players.player import Player

FileAccessRule: TypeAlias = Callable[["Player"], bool]


@dataclass(frozen=True)
class VirtualFile:
    stable_id: str
    path: str
    revision: str
    content: bytes
    media_type: str = "text/plain"
    access_rule: FileAccessRule | None = None
