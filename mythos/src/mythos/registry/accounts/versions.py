from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from mythos.registry.catalog_snapshots import TemplateSnapshotEntry, fingerprint

VirtualAccountVersion: TypeAlias = str
VirtualAccountCatalogVersion: TypeAlias = str


def virtual_account_version(
    account_id: str,
    display_name: str,
    permission: int,
    metadata: Mapping[str, object],
) -> VirtualAccountVersion:
    return fingerprint(
        "vat1_",
        {
            "schema": 1,
            "account_id": account_id,
            "display_name": display_name,
            "permission": permission,
            "metadata": dict(metadata),
        },
    )


def virtual_account_catalog_version(
    entries: tuple[TemplateSnapshotEntry, ...],
) -> VirtualAccountCatalogVersion:
    ordered = tuple(sorted(entries, key=lambda entry: (entry.kind, entry.template_id)))
    return fingerprint("vac1_", [entry.as_dict() for entry in ordered])
