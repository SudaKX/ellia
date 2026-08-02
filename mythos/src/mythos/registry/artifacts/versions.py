from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias, TypeVar


_CALLBACK_NAMESPACE = uuid.UUID("4f5b2b0b-34d7-5d8b-87f1-61ba2f1a2959")
_Callback = TypeVar("_Callback", bound=Callable[..., object])
ArtifactVersion: TypeAlias = str
ArtifactNodeVersion: TypeAlias = str
TemplateVersion: TypeAlias = str


def module_handler(module: str) -> Callable[[int], Callable[[_Callback], _Callback]]:
    if not module:
        raise ValueError("Module handlers require a module ID.")

    def handler(revision: int) -> Callable[[_Callback], _Callback]:
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise ValueError("Module handler revisions must be positive integers.")

        def decorate(callback: _Callback) -> _Callback:
            key = f"{module}:{callback.__qualname__}:{revision}"
            setattr(callback, "__callback_id__", str(uuid.uuid5(_CALLBACK_NAMESPACE, key)))
            return callback

        return decorate

    return handler


def callback_id(callback: Callable[..., object], *, field_name: str) -> str:
    value = getattr(callback, "__callback_id__", None)
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be decorated with module_handler().")
    try:
        return str(uuid.UUID(value))
    except ValueError as error:
        raise ValueError(f"{field_name} has an invalid callback ID.") from error


def artifact_version(
    artifact_id: str,
    media_type: str,
    download_name: str,
    generator: Callable[..., object],
) -> ArtifactVersion:
    return _fingerprint(
        "av1_",
        {
            "schema": 1,
            "artifact_id": artifact_id,
            "media_type": media_type,
            "download_name": download_name,
            "generator_callback_id": callback_id(generator, field_name="Artifact generator"),
        },
    )


def artifact_node_version(
    stable_id: str,
    artifact_locator: str,
    path: str,
    display: Mapping[str, object],
    hidden: bool,
    download_name: str | None,
    node_generator: Callable[..., object],
    access_rule: Callable[..., object] | None,
) -> ArtifactNodeVersion:
    return _fingerprint(
        "anv1_",
        {
            "schema": 1,
            "stable_id": stable_id,
            "artifact_locator": artifact_locator,
            "path": path,
            "display": dict(display),
            "hidden": hidden,
            "download_name": download_name,
            "node_generator_callback_id": callback_id(
                node_generator,
                field_name="Artifact node generator",
            ),
            "access_rule_callback_id": (
                callback_id(access_rule, field_name="Artifact node access rule")
                if access_rule is not None
                else None
            ),
        },
    )


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


def template_snapshot(entries: tuple[TemplateSnapshotEntry, ...]) -> TemplateSnapshot:
    ordered = tuple(sorted(entries, key=lambda entry: (entry.kind, entry.template_id)))
    return TemplateSnapshot(
        _fingerprint("tv1_", [entry.as_dict() for entry in ordered]),
        ordered,
    )


def _fingerprint(prefix: str, value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    return prefix + hashlib.sha256(payload).hexdigest()
