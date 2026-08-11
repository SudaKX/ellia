from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, TypeAlias

if TYPE_CHECKING:
    from mythos.players.player import Player

NodeAccessRule: TypeAlias = Callable[["Player"], bool]
StaticNodeVersion: TypeAlias = str


@dataclass(frozen=True)
class NodeDisplayParams:
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

    def __post_init__(self) -> None:
        if not self.key or self.key.startswith("/") or "\\" in self.key:
            raise ValueError("Object keys must be non-empty relative paths.")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.content_digest):
            raise ValueError("Object content digests must be lowercase SHA-256 values.")
        if not self.media_type or any(character in "\r\n" for character in self.media_type):
            raise ValueError("Object media types cannot contain control characters.")
        if self.size_bytes < 0:
            raise ValueError("Object sizes cannot be negative.")


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


def is_canonical_source_module(value: str) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and "/" not in value
        and "\\" not in value
        and ":" not in value
        and value not in {".", ".."}
    )


def is_canonical_source_relative_path(value: str) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith("/")
        and "\\" not in value
        and ":" not in value
        and all(part and part not in {".", ".."} for part in value.split("/"))
    )


class VirtualNode(ABC):
    def __init__(
        self,
        stable_id: str,
        path: str,
        version: str,
        display: NodeDisplayParams,
        access_rule: NodeAccessRule | None = None,
        hidden: bool = False,
        download_name: str | None = None,
    ) -> None:
        self.stable_id = stable_id
        self.path = path
        self.version = version
        self.display = display
        self.access_rule = access_rule
        self.hidden = hidden
        self.download_name = download_name

    @property
    @abstractmethod
    def is_file(self) -> bool: ...


class StaticNode(VirtualNode):
    def __init__(
        self,
        stable_id: str,
        path: str,
        version: str,
        display: NodeDisplayParams,
        access_rule: NodeAccessRule | None = None,
        hidden: bool = False,
        download_name: str | None = None,
        source_locator: str | None = None,
    ) -> None:
        super().__init__(
            stable_id,
            path,
            version,
            display,
            access_rule,
            hidden,
            download_name,
        )
        self.source_locator = source_locator

    @property
    def is_file(self) -> bool:
        return self.source_locator is not None


@dataclass(frozen=True)
class StaticNodeSpec:
    """Registration-time static node declaration resolved into a StaticNode."""

    stable_id: str
    path: str
    display: NodeDisplayParams
    access_rule: NodeAccessRule | None = None
    hidden: bool = False
    download_name: str | None = None
    source_locator: str | None = None

    @classmethod
    def file(
        cls,
        stable_id: str,
        path: str,
        source_locator: str,
        download_name: str,
        access_rule: NodeAccessRule | None = None,
        *,
        display: NodeDisplayParams,
        hidden: bool = False,
    ) -> StaticNodeSpec:
        return cls(
            stable_id=stable_id,
            path=path,
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
        access_rule: NodeAccessRule | None = None,
        *,
        display: NodeDisplayParams,
        hidden: bool = False,
    ) -> StaticNodeSpec:
        return cls(
            stable_id=stable_id,
            path=path,
            display=display,
            access_rule=access_rule,
            hidden=hidden,
        )

    def to_runtime_node(self) -> StaticNode:
        return StaticNode(
            self.stable_id,
            self.path,
            "",
            self.display,
            self.access_rule,
            self.hidden,
            self.download_name,
            self.source_locator,
        )


def is_safe_download_name(value: str) -> bool:
    return isinstance(value, str) and bool(value) and all(
        32 <= ord(character) <= 126 and character not in '"/\\'
        for character in value
    )
