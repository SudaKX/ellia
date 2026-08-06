from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TypeAlias

from mythos.registry.callbacks import callback_id
from mythos.registry.catalog_snapshots import (
    TemplateSnapshotEntry,
    TemplateVersion,
    fingerprint,
)


ArtifactVersion: TypeAlias = str
ArtifactNodeVersion: TypeAlias = str


def artifact_version(
    artifact_id: str,
    media_type: str,
    download_name: str,
    generator: Callable[..., object],
) -> ArtifactVersion:
    return fingerprint(
        "atv1_",
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
    artifact_template_version: str,
    path: str,
    display: Mapping[str, object],
    hidden: bool,
    download_name: str | None,
    node_generator: Callable[..., object],
    access_rule: Callable[..., object] | None,
) -> ArtifactNodeVersion:
    if not artifact_template_version:
        raise ValueError("Artifact node versions require an Artifact template version.")
    return fingerprint(
        "antv2_",
        {
            "schema": 2,
            "stable_id": stable_id,
            "artifact_locator": artifact_locator,
            "artifact_template_version": artifact_template_version,
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
