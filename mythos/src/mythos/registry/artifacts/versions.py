from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from typing import TypeAlias, TypeVar

from mythos.registry.catalog_snapshots import (
    TemplateSnapshot,
    TemplateSnapshotEntry,
    TemplateVersion,
    fingerprint,
    template_snapshot,
)


_CALLBACK_NAMESPACE = uuid.UUID("4f5b2b0b-34d7-5d8b-87f1-61ba2f1a2959")
_Callback = TypeVar("_Callback", bound=Callable[..., object])
ArtifactVersion: TypeAlias = str
ArtifactNodeVersion: TypeAlias = str


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
    return fingerprint(
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
    return fingerprint(
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
