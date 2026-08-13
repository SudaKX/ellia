from __future__ import annotations

from collections.abc import Mapping
from typing import TypeAlias

from mythos.registry.catalog_snapshots import TemplateSnapshotEntry, fingerprint

CreditVersion: TypeAlias = str
CreditCatalogVersion: TypeAlias = str


def credit_template_version(
    credit_id: str,
    display_name: str,
    metadata: Mapping[str, object],
) -> CreditVersion:
    return fingerprint(
        "ct1_",
        {
            "schema": 1,
            "credit_id": credit_id,
            "display_name": display_name,
            "metadata": dict(metadata),
        },
    )


def credit_catalog_version(
    entries: tuple[TemplateSnapshotEntry, ...],
) -> CreditCatalogVersion:
    ordered = tuple(sorted(entries, key=lambda entry: (entry.kind, entry.template_id)))
    return fingerprint("cc1_", [entry.as_dict() for entry in ordered])
