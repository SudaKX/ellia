from __future__ import annotations

from dataclasses import dataclass
import re

from mythos.registry.callbacks import callback_id
from mythos.registry.catalog_snapshots import fingerprint
from mythos.registry.files.definitions import FileReference, NodeAccessRule, is_safe_download_name


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
    access_rule: NodeAccessRule | None = None

    def __post_init__(self) -> None:
        if not self.stable_id or len(self.stable_id) > 128:
            raise ValueError("Hints require a stable ID.")
        if not is_safe_download_name(self.download_name):
            raise ValueError("Hint download names must be safe single path segments.")
        if isinstance(self.vtb_cost, bool) or not isinstance(self.vtb_cost, int) or self.vtb_cost <= 0:
            raise ValueError("Hint VTB costs must be positive integers.")
        if self.access_rule is not None and not callable(self.access_rule):
            raise ValueError("Hint access rules must be callable.")


def hint_version(hint: Hint, *, source_file_hash: str, source_media_type: str) -> str:
    return fingerprint(
        "hv1_",
        {
            "schema": 1,
            "stable_id": hint.stable_id,
            "source_locator": hint.source.source_locator,
            "source_file_hash": source_file_hash,
            "source_media_type": source_media_type,
            "download_name": hint.download_name,
            "display": hint.display.as_dict(),
            "vtb_cost": hint.vtb_cost,
            "access_rule_callback_id": (
                callback_id(hint.access_rule, field_name="Hint access rule")
                if hint.access_rule is not None
                else None
            ),
        },
    )
