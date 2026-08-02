from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

from mythos.registry.files.definitions import DisplayParams, NodeAccessRule, VirtualNode
from mythos.registry.artifacts.versions import artifact_node_version, artifact_version, callback_id

if TYPE_CHECKING:
    from mythos.players.player import Player


class ArtifactGenerationContext(Protocol):
    @property
    def player(self) -> Player: ...


@dataclass(frozen=True)
class RawArtifact:
    data: bytes
    meta: dict[str, Any] = field(default_factory=dict)


ArtifactGenerator: TypeAlias = Callable[[ArtifactGenerationContext], Awaitable["RawArtifact"]]
ArtifactNodeGenerator: TypeAlias = Callable[[ArtifactGenerationContext, "ArtifactNode"], Awaitable["ArtifactNode"]]


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
        if not self.download_name:
            raise ValueError("Artifact templates require a download name.")
        callback_id(self.generator, field_name="Artifact generator")

    @property
    def version(self) -> str:
        return artifact_version(
            self.artifact_id,
            self.media_type,
            self.download_name,
            self.generator,
        )


@dataclass(frozen=True, kw_only=True)
class ArtifactNodeTemplate:
    stable_id: str
    path: str
    display: DisplayParams
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
        callback_id(self.node_generator, field_name="Artifact node generator")
        if self.access_rule is not None:
            callback_id(self.access_rule, field_name="Artifact node access rule")

    @property
    def is_file(self) -> bool:
        return True

    @property
    def version(self) -> str:
        return artifact_node_version(
            self.stable_id,
            self.artifact_locator,
            self.path,
            self.display.as_dict(),
            self.hidden,
            self.download_name,
            self.node_generator,
            self.access_rule,
        )

    def to_runtime_node(self) -> ArtifactNode:
        return ArtifactNode(
            stable_id=self.stable_id,
            path=self.path,
            version=self.version,
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
        display: DisplayParams,
        artifact_locator: str,
        access_rule: NodeAccessRule | None = None,
        hidden: bool = False,
        download_name: str | None = None,
    ) -> None:
        object.__setattr__(self, "stable_id", stable_id)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "display", display)
        object.__setattr__(self, "access_rule", access_rule)
        object.__setattr__(self, "hidden", hidden)
        object.__setattr__(self, "download_name", download_name)
        object.__setattr__(self, "artifact_locator", artifact_locator)
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_initialized", False) and name in {"stable_id", "artifact_locator", "version"}:
            raise AttributeError(f"{name} is immutable after initialization.")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_initialized", False):
            raise AttributeError("Artifact nodes are immutable after initialization.")
        object.__delattr__(self, name)

    @property
    def is_file(self) -> bool:
        return True
