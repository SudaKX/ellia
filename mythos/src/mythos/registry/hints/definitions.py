from __future__ import annotations

from dataclasses import dataclass
import re

from mythos.registry.files.definitions import FileReference, NodeAccessRule


@dataclass(frozen=True)
class HintDisplayParams:
    title: str
    teaser: str | None = None
    icon: str | None = None
    sort_order: int = 0

    def __post_init__(self) -> None:
        if not self.title or any(character in "\r\n" for character in self.title):
            raise ValueError("Hint titles must be non-empty single-line strings.")
        if self.teaser is not None and any(character in "\r\n" for character in self.teaser):
            raise ValueError("Hint teasers cannot contain newlines.")
        if self.icon is not None and not re.fullmatch(r"[a-z][a-z0-9-]*", self.icon):
            raise ValueError("Hint icons must be semantic lowercase tokens.")
        if isinstance(self.sort_order, bool) or not isinstance(self.sort_order, int):
            raise ValueError("Hint display sort orders must be integers.")

    def as_dict(self) -> dict[str, str | int | None]:
        return {
            "title": self.title,
            "teaser": self.teaser,
            "icon": self.icon,
            "sort_order": self.sort_order,
        }


@dataclass(frozen=True)
class Hint:
    stable_id: str
    source: FileReference
    download_name: str
    display: HintDisplayParams
    vtb_cost: int
    revision: int
    access_rule: NodeAccessRule | None = None

    def __post_init__(self) -> None:
        if not self.stable_id or len(self.stable_id) > 128:
            raise ValueError("Hints require a stable ID.")
        if not self.download_name or any(character in "\\/\r\n" for character in self.download_name):
            raise ValueError("Hint download names must be safe single path segments.")
        if isinstance(self.vtb_cost, bool) or not isinstance(self.vtb_cost, int) or self.vtb_cost <= 0:
            raise ValueError("Hint VTB costs must be positive integers.")
        if isinstance(self.revision, bool) or not isinstance(self.revision, int) or self.revision <= 0:
            raise ValueError("Hint revisions must be positive integers.")
        if self.access_rule is not None and not callable(self.access_rule):
            raise ValueError("Hint access rules must be callable.")

    @property
    def version(self) -> str:
        return f"h1:{self.revision}"
