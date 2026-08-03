from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from mythos.registry.accounts.versions import virtual_account_version
from mythos.registry.catalog_snapshots import TemplateSnapshotEntry


@dataclass(frozen=True)
class VirtualAccountTemplate:
    """A virtual account definition with JSON-serializable, non-sensitive metadata."""

    account_id: str
    display_name: str
    permission: int
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.account_id:
            raise ValueError("Virtual account templates require an account ID.")
        if not self.display_name:
            raise ValueError("Virtual account templates require a display name.")
        if type(self.permission) is not int:
            raise ValueError("Virtual account permissions must be integers.")
        try:
            serialized_metadata = json.dumps(dict(self.metadata), ensure_ascii=True, allow_nan=False)
        except (TypeError, ValueError) as error:
            raise ValueError("Virtual account metadata must be JSON serializable.") from error
        object.__setattr__(self, "metadata", MappingProxyType(json.loads(serialized_metadata)))

    @property
    def version(self) -> str:
        return virtual_account_version(
            self.account_id,
            self.display_name,
            self.permission,
            self.metadata,
        )

    def snapshot_entry(self) -> TemplateSnapshotEntry:
        return TemplateSnapshotEntry(
            kind="virtual_account",
            template_id=self.account_id,
            version=self.version,
            definition={
                "account_id": self.account_id,
                "display_name": self.display_name,
                "permission": self.permission,
                "metadata": dict(self.metadata),
            },
        )
