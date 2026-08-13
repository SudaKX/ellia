from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from mythos.registry.catalog_snapshots import fingerprint
from mythos.registry.files.definitions import StaticNode


@dataclass
class FileCatalog:
    version: str

    @classmethod
    def build(
        cls,
        nodes: Mapping[str, StaticNode],
        file_id_key_fingerprint: str,
    ) -> FileCatalog:
        return cls(
            fingerprint(
                "fcv1_",
                {
                    "schema": 1,
                    "file_id_key_fingerprint": file_id_key_fingerprint,
                    "entries": [
                        (node.stable_id, node.version)
                        for node in sorted(nodes.values(), key=lambda item: item.stable_id)
                    ],
                },
            )
        )
