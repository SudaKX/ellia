from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from mythos.players.player import Player

NodeAccessRule: TypeAlias = Callable[["Player"], bool]


@dataclass(frozen=True)
class ObjectReference:
    key: str
    content_digest: str
    media_type: str
    size_bytes: int
    version_id: str

    def __post_init__(self) -> None:
        if not self.key or self.key.startswith("/") or "\\" in self.key:
            raise ValueError("Object keys must be non-empty relative paths.")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.content_digest):
            raise ValueError("Object content digests must be lowercase SHA-256 values.")
        if not self.media_type or any(character in "\r\n" for character in self.media_type):
            raise ValueError("Object media types cannot contain control characters.")
        if self.size_bytes < 0:
            raise ValueError("Object sizes cannot be negative.")
        if not self.version_id or any(character in "\r\n" for character in self.version_id):
            raise ValueError("Object version IDs cannot be empty or contain control characters.")


@dataclass(frozen=True)
class FileContent:
    object_ref: ObjectReference
    download_name: str


@dataclass(frozen=True)
class VirtualNode:
    stable_id: str
    path: str
    revision: str
    content: FileContent | None = None
    access_rule: NodeAccessRule | None = None
