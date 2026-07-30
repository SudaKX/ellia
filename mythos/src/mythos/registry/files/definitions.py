from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from mythos.players.player import Player

NodeAccessRule: TypeAlias = Callable[["Player"], bool]


@dataclass(frozen=True)
class DisplayParams:
    label: str
    description: str | None = None
    icon: str | None = None
    sort_order: int = 0

    def __post_init__(self) -> None:
        if not self.label or any(character in "\r\n" for character in self.label):
            raise ValueError("Display labels must be non-empty single-line strings.")
        if self.description is not None and any(character in "\r\n" for character in self.description):
            raise ValueError("Display descriptions cannot contain newlines.")
        if self.icon is not None and not re.fullmatch(r"[a-z][a-z0-9-]*", self.icon):
            raise ValueError("Display icons must be semantic lowercase tokens.")
        if isinstance(self.sort_order, bool) or not isinstance(self.sort_order, int):
            raise ValueError("Display sort orders must be integers.")

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "label": self.label,
            "description": self.description,
            "icon": self.icon,
            "sort_order": self.sort_order,
        }


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
    content_token: str


@dataclass(frozen=True)
class FileReference:
    module: str
    relative_path: str
    media_type: str

    @property
    def source_locator(self) -> str:
        return f"{self.module}:{self.relative_path}"


@dataclass(frozen=True)
class VirtualNode(ABC):
    stable_id: str
    path: str
    revision: str
    display: DisplayParams
    access_rule: NodeAccessRule | None = None
    hidden: bool = False
    download_name: str | None = None

    @property
    @abstractmethod
    def is_file(self) -> bool: ...


@dataclass(frozen=True)
class StaticNode(VirtualNode):
    source_locator: str | None = None

    @classmethod
    def file(
        cls,
        stable_id: str,
        path: str,
        revision: str,
        source_locator: str,
        download_name: str,
        access_rule: NodeAccessRule | None = None,
        *,
        display: DisplayParams,
        hidden: bool = False,
    ) -> StaticNode:
        return cls(
            stable_id=stable_id,
            path=path,
            revision=revision,
            display=display,
            access_rule=access_rule,
            hidden=hidden,
            download_name=download_name,
            source_locator=source_locator,
        )

    @classmethod
    def directory(
        cls,
        stable_id: str,
        path: str,
        revision: str,
        access_rule: NodeAccessRule | None = None,
        *,
        display: DisplayParams,
        hidden: bool = False,
    ) -> StaticNode:
        return cls(
            stable_id=stable_id,
            path=path,
            revision=revision,
            display=display,
            access_rule=access_rule,
            hidden=hidden,
            download_name=None,
            source_locator=None,
        )

    @property
    def is_file(self) -> bool:
        return self.source_locator is not None
