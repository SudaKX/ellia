from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeAlias

from mythos.registry.files.definitions import (
    NodeAccessRule,
    NodeDisplayParams,
    VirtualNode,
    is_safe_download_name,
)
from mythos.registry.artifacts.versions import artifact_node_version, artifact_version, callback_id
from mythos.registry.callbacks import validate_callback
from mythos.registry.catalog_snapshots import TemplateSnapshotEntry

if TYPE_CHECKING:
    from mythos.players.player import Player

@dataclass(frozen=True)
class RawArtifact:
    data: bytes
    meta: dict[str, Any] = field(default_factory=dict)


ArtifactGenerator: TypeAlias = Callable[["Player"], Awaitable["RawArtifact"]]
ArtifactNodeGenerator: TypeAlias = Callable[["Player", Mapping[str, Any], "ArtifactNode"], Awaitable["ArtifactNode"]]


def _is_canonical_virtual_path(path: str) -> bool:
    if not path.startswith("/") or path == "/" or path.endswith("/") or "\\" in path:
        return False
    parts = path.split("/")[1:]
    return all(part and part not in {".", ".."} for part in parts)


@dataclass(frozen=True)
class ArtifactTemplate:
    artifact_id: str
    media_type: str
    download_name: str
    generator: ArtifactGenerator

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("Artifact templates require an artifact ID.")
        if not self.media_type:
            raise ValueError("Artifact templates require a media type.")
        if not is_safe_download_name(self.download_name):
            raise ValueError("Artifact templates require a safe download name.")
        validate_callback(
            self.generator,
            field_name="Artifact generator",
            parameter_count=1,
            asynchronous=True,
        )

    @property
    def version(self) -> str:
        return artifact_version(
            self.artifact_id,
            self.media_type,
            self.download_name,
            self.generator,
        )

    def snapshot_entry(self) -> TemplateSnapshotEntry:
        return TemplateSnapshotEntry(
            kind="artifact",
            template_id=self.artifact_id,
            version=self.version,
            definition={
                "artifact_id": self.artifact_id,
                "media_type": self.media_type,
                "download_name": self.download_name,
                "generator_callback_id": callback_id(
                    self.generator,
                    field_name="Artifact generator",
                ),
            },
        )


@dataclass(frozen=True, kw_only=True)
class ArtifactNodeTemplate:
    stable_id: str
    path: str
    display: NodeDisplayParams
    artifact_locator: str
    node_generator: ArtifactNodeGenerator
    access_rule: NodeAccessRule | None = None
    hidden: bool = False
    download_name: str | None = None

    def __post_init__(self) -> None:
        if not self.stable_id:
            raise ValueError("Artifact node templates require a stable ID.")
        if not _is_canonical_virtual_path(self.path):
            raise ValueError("Artifact node templates require a canonical absolute path.")
        if not self.artifact_locator:
            raise ValueError("Artifact node templates require an artifact locator.")
        if not isinstance(self.hidden, bool):
            raise ValueError("Artifact node hidden flags must be booleans.")
        if self.download_name is not None and not is_safe_download_name(self.download_name):
            raise ValueError("Artifact node templates require a safe download name.")
        validate_callback(
            self.node_generator,
            field_name="Artifact node generator",
            parameter_count=3,
            asynchronous=True,
        )
        if self.access_rule is not None:
            validate_callback(
                self.access_rule,
                field_name="Artifact node access rule",
                parameter_count=1,
                asynchronous=False,
                require_dependencies=True,
            )

    @property
    def is_file(self) -> bool:
        return True

    def version_for(self, artifact_template_version: str) -> str:
        return artifact_node_version(
            self.stable_id,
            self.artifact_locator,
            artifact_template_version,
            self.path,
            self.display.as_dict(),
            self.hidden,
            self.download_name,
            self.node_generator,
            self.access_rule,
        )

    def snapshot_entry(self, version: str) -> TemplateSnapshotEntry:
        return TemplateSnapshotEntry(
            kind="artifact_node",
            template_id=self.stable_id,
            version=version,
            definition={
                "stable_id": self.stable_id,
                "artifact_locator": self.artifact_locator,
                "path": self.path,
                "display": self.display.as_dict(),
                "hidden": self.hidden,
                "download_name": self.download_name,
                "node_generator_callback_id": callback_id(
                    self.node_generator,
                    field_name="Artifact node generator",
                ),
                "access_rule_callback_id": (
                    callback_id(
                        self.access_rule,
                        field_name="Artifact node access rule",
                    )
                    if self.access_rule is not None
                    else None
                ),
            },
        )

    def to_runtime_node(self, version: str) -> ArtifactNode:
        return ArtifactNode(
            stable_id=self.stable_id,
            path=self.path,
            version=version,
            display=self.display,
            access_rule=self.access_rule,
            hidden=self.hidden,
            download_name=self.download_name,
            artifact_locator=self.artifact_locator,
        )


class ArtifactNode(VirtualNode):
    def __init__(
        self,
        stable_id: str,
        path: str,
        version: str,
        display: NodeDisplayParams,
        artifact_locator: str,
        access_rule: NodeAccessRule | None = None,
        hidden: bool = False,
        download_name: str | None = None,
    ) -> None:
        super().__init__(
            stable_id,
            path,
            version,
            display,
            access_rule,
            hidden,
            download_name,
        )
        self.artifact_locator = artifact_locator

    @property
    def is_file(self) -> bool:
        return True
