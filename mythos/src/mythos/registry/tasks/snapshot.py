from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from mythos.registry.catalog_snapshots import fingerprint


@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    handler_ids: tuple[str, ...]
    registry_version: str

    @classmethod
    def from_ids(cls, handler_ids: tuple[str, ...]) -> TaskSnapshot:
        ordered = tuple(sorted(handler_ids))
        return cls(ordered, fingerprint("tsk1_", ordered))

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "registry_version": self.registry_version,
            "handler_ids": list(self.handler_ids),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> TaskSnapshot:
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported task snapshot schema.")
        registry_version = payload.get("registry_version")
        handler_ids = payload.get("handler_ids")
        if not isinstance(registry_version, str) or not isinstance(handler_ids, list):
            raise ValueError("Task snapshot is malformed.")
        if any(not isinstance(handler_id, str) for handler_id in handler_ids):
            raise ValueError("Task snapshot handler IDs are malformed.")
        snapshot = cls.from_ids(tuple(handler_ids))
        if snapshot.registry_version != registry_version:
            raise ValueError("Task snapshot registry version does not match its handler IDs.")
        return snapshot
