from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from mythos.registry.catalog_snapshots import TemplateSnapshotEntry
from mythos.registry.credits.versions import credit_template_version

CREDIT_VTB_ID = "vtb"

_CREDIT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


def is_canonical_credit_id(credit_id: str) -> bool:
    return isinstance(credit_id, str) and bool(_CREDIT_ID_PATTERN.fullmatch(credit_id))


@dataclass(frozen=True)
class CreditTemplate:
    """A credit definition with JSON-serializable, non-sensitive metadata."""

    credit_id: str
    display_name: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not is_canonical_credit_id(self.credit_id):
            raise ValueError("Credit IDs must be lowercase slugs up to 128 characters.")
        if not self.display_name:
            raise ValueError("Credit templates require a display name.")
        try:
            serialized_metadata = json.dumps(dict(self.metadata), ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Credit metadata must be JSON serializable.") from error
        object.__setattr__(self, "metadata", MappingProxyType(json.loads(serialized_metadata)))

    @property
    def version(self) -> str:
        return credit_template_version(self.credit_id, self.display_name, self.metadata)

    def snapshot_entry(self) -> TemplateSnapshotEntry:
        return TemplateSnapshotEntry(
            kind="credit",
            template_id=self.credit_id,
            version=self.version,
            definition={
                "credit_id": self.credit_id,
                "display_name": self.display_name,
                "metadata": dict(self.metadata),
            },
        )
