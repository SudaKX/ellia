from __future__ import annotations

from abc import ABC
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeAlias

from mythos.registry.files.definitions import DisplayParams, NodeAccessRule, VirtualNode

if TYPE_CHECKING:
    from mythos.players.context import CommandContext


@dataclass(frozen=True)
class RawArtifact:
    data: bytes
    meta: dict[str, Any] = field(default_factory=dict)


ArtifactGenerator: TypeAlias = Callable[["CommandContext"], Awaitable["RawArtifact"]]
ArtifactNodeGenerator: TypeAlias = Callable[["CommandContext", "ArtifactNode"], Awaitable["ArtifactNode"]]


def _is_canonical_virtual_path(path: str) -> bool:
    if not path.startswith("/") or path == "/" or path.endswith("/") or "\\" in path:
        return False
    parts = path.split("/")[1:]
    return all(part and part not in {".", ".."} for part in parts)


@dataclass(frozen=True)
class ArtifactTemplate:
    artifact_id: str
    revision: str
    media_type: str
    download_name: str
    generator: ArtifactGenerator

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("Artifact templates require an artifact ID.")
        if not self.revision:
            raise ValueError("Artifact templates require a revision.")
        if not self.media_type:
            raise ValueError("Artifact templates require a media type.")
        if not self.download_name:
            raise ValueError("Artifact templates require a download name.")


@dataclass(frozen=True, kw_only=True)
class ArtifactNodeTemplate(VirtualNode):
    artifact_locator: str
    node_generator: ArtifactNodeGenerator

    def __post_init__(self) -> None:
        if not self.stable_id:
            raise ValueError("Artifact node templates require a stable ID.")
        if not self.revision:
            raise ValueError("Artifact node templates require a revision.")
        if not _is_canonical_virtual_path(self.path):
            raise ValueError("Artifact node templates require a canonical absolute path.")
        if not self.artifact_locator:
            raise ValueError("Artifact node templates require an artifact locator.")
        if not isinstance(self.hidden, bool):
            raise ValueError("Artifact node hidden flags must be booleans.")

    @property
    def is_file(self) -> bool:
        return True

    def to_runtime_node(self) -> ArtifactNode:
        return ArtifactNode(
            stable_id=self.stable_id,
            path=self.path,
            revision=self.revision,
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
        revision: str,
        display: DisplayParams,
        artifact_locator: str,
        access_rule: NodeAccessRule | None = None,
        hidden: bool = False,
        download_name: str | None = None,
    ) -> None:
        object.__setattr__(self, "stable_id", stable_id)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "display", display)
        object.__setattr__(self, "access_rule", access_rule)
        object.__setattr__(self, "hidden", hidden)
        object.__setattr__(self, "download_name", download_name)
        object.__setattr__(self, "artifact_locator", artifact_locator)
        object.__setattr__(self, "_initialized", True)

    def __setattr__(self, name: str, value: object) -> None:
        if getattr(self, "_initialized", False) and name in {"stable_id", "artifact_locator"}:
            raise AttributeError(f"{name} is immutable after initialization.")
        object.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if getattr(self, "_initialized", False):
            raise AttributeError("Artifact nodes are immutable after initialization.")
        object.__delattr__(self, name)

    @property
    def is_file(self) -> bool:
        return True
