from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias


TemplateVersion: TypeAlias = str


@dataclass(frozen=True)
class TemplateSnapshotEntry:
    kind: str
    template_id: str
    version: str
    definition: Mapping[str, object]

    def as_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "template_id": self.template_id,
            "version": self.version,
            "definition": dict(self.definition),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> TemplateSnapshotEntry:
        kind = payload.get("kind")
        template_id = payload.get("template_id")
        version = payload.get("version")
        definition = payload.get("definition")
        if not all(isinstance(value, str) for value in (kind, template_id, version)):
            raise ValueError("Template snapshot entry is malformed.")
        if not isinstance(definition, dict):
            raise ValueError("Template snapshot definition is malformed.")
        return cls(kind, template_id, version, definition)


@dataclass(frozen=True)
class TemplateSnapshot:
    template_version: TemplateVersion
    entries: tuple[TemplateSnapshotEntry, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "template_version": self.template_version,
            "entries": [entry.as_dict() for entry in self.entries],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> TemplateSnapshot:
        if payload.get("schema_version") != 1:
            raise ValueError("Unsupported template snapshot schema.")
        template_version = payload.get("template_version")
        entries = payload.get("entries")
        if not isinstance(template_version, str) or not isinstance(entries, list):
            raise ValueError("Template snapshot is malformed.")
        parsed_entries = tuple(
            TemplateSnapshotEntry.from_dict(entry)
            for entry in entries
            if isinstance(entry, dict)
        )
        if len(parsed_entries) != len(entries):
            raise ValueError("Template snapshot entry is malformed.")
        return cls(template_version, parsed_entries)


def fingerprint(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return prefix + hashlib.sha256(payload).hexdigest()


def template_snapshot(
    entries: Iterable[TemplateSnapshotEntry],
    *,
    prefix: str = "tv1_",
) -> TemplateSnapshot:
    ordered = tuple(sorted(entries, key=lambda entry: (entry.kind, entry.template_id)))
    return TemplateSnapshot(
        fingerprint(prefix, [entry.as_dict() for entry in ordered]),
        ordered,
    )


def template_snapshot_changed_keys(
    previous: TemplateSnapshot,
    current: TemplateSnapshot,
) -> frozenset[tuple[str, str]]:
    previous_entries = {(entry.kind, entry.template_id): entry for entry in previous.entries}
    current_entries = {(entry.kind, entry.template_id): entry for entry in current.entries}
    return frozenset(
        key
        for key in previous_entries.keys() | current_entries.keys()
        if previous_entries.get(key) != current_entries.get(key)
    )
