from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from mythos.core.file_ids import FileIdCodec
from mythos.registry.accounts import VirtualAccountCatalog, VirtualAccountRegistry
from mythos.registry.artifacts import ArtifactCatalog, ArtifactRegistry
from mythos.registry.errors import DuplicateStableIdError
from mythos.registry.files import FileRegistry, FileTree
from mythos.registry.lifecycle import LifecycleCatalog, LifecycleRegistry
from mythos.registry.progress import ProgressGraph, ProgressRegistry
from mythos.registry.scripts import ScriptCatalog, ScriptRegistry
from mythos.registry.validations import ValidationCatalog, ValidationRegistry

if TYPE_CHECKING:
    from mythos.services.files.static_assets import StaticAssetPublisher


@dataclass(frozen=True)
class RuntimeCatalogs:
    files: FileTree
    progress: ProgressGraph
    scripts: ScriptCatalog
    validations: ValidationCatalog
    artifacts: ArtifactCatalog
    accounts: VirtualAccountCatalog
    lifecycle: LifecycleCatalog


class RegistryBundle:
    def __init__(self, puzzle_root: Path | None = None) -> None:
        self.files = FileRegistry(puzzle_root)
        self.progress = ProgressRegistry()
        self.scripts = ScriptRegistry()
        self.validations = ValidationRegistry()
        self.artifacts = ArtifactRegistry()
        self.accounts = VirtualAccountRegistry()
        self.lifecycle = LifecycleRegistry()
        self._catalogs: RuntimeCatalogs | None = None

    def configure_puzzle_root(self, puzzle_root: Path) -> None:
        self.files.configure_puzzle_root(puzzle_root)

    def freeze(self, file_ids: FileIdCodec) -> RuntimeCatalogs:
        if self._catalogs is not None:
            if self._catalogs.files.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RuntimeError("RegistryBundle is already frozen with a different file ID key.")
            return self._catalogs
        static_ids = set(self.files._nodes_by_stable_id)
        artifact_ids = set(self.artifacts._node_templates)
        duplicates = static_ids & artifact_ids
        if duplicates:
            raise DuplicateStableIdError(next(iter(sorted(duplicates))))
        self._catalogs = RuntimeCatalogs(
            files=self.files.freeze(file_ids),
            progress=self.progress.freeze(),
            scripts=self.scripts.freeze(),
            validations=self.validations.freeze(),
            artifacts=self.artifacts.freeze(),
            accounts=self.accounts.freeze(),
            lifecycle=self.lifecycle.freeze(),
        )
        return self._catalogs

    async def materialize_static_files(self, publisher: StaticAssetPublisher) -> None:
        if self._catalogs is not None:
            return
        if self.files.is_materialized:
            return
        self.files.materialize_static_files(await publisher.materialize(self.files.sources))
