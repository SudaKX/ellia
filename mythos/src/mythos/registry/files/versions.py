from __future__ import annotations

from mythos.registry.callbacks import callback_id
from mythos.registry.catalog_snapshots import fingerprint
from mythos.registry.files.definitions import ObjectReference, StaticNode


def static_node_version(node: StaticNode, content: ObjectReference | None) -> str:
    return fingerprint(
        "snv1_",
        {
            "schema": 1,
            "stable_id": node.stable_id,
            "kind": "file" if node.is_file else "directory",
            "path": node.path,
            "display": node.display.as_dict(),
            "hidden": node.hidden,
            "source_locator": node.source_locator,
            "source_file_hash": content.content_digest if content is not None else None,
            "source_media_type": content.media_type if content is not None else None,
            "download_name": node.download_name,
            "access_rule_callback_id": (
                callback_id(node.access_rule, field_name="Static node access rule")
                if node.access_rule is not None
                else None
            ),
        },
    )
