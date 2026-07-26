from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from mythos.core.file_ids import FileIdCodec
from mythos.registry.files import FileRegistry, FileTree
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


class RegistryBundle:
    def __init__(self) -> None:
        self.files = FileRegistry()
        self.progress = ProgressRegistry()
        self.scripts = ScriptRegistry()
        self.validations = ValidationRegistry()
        self._catalogs: RuntimeCatalogs | None = None

    def freeze(self, file_ids: FileIdCodec) -> RuntimeCatalogs:
        if self._catalogs is not None:
            if self._catalogs.files.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RuntimeError("RegistryBundle is already frozen with a different file ID key.")
            return self._catalogs
        self._catalogs = RuntimeCatalogs(
            files=self.files.freeze(file_ids),
            progress=self.progress.freeze(),
            scripts=self.scripts.freeze(),
            validations=self.validations.freeze(),
        )
        return self._catalogs

    async def materialize_static_files(self, publisher: StaticAssetPublisher) -> None:
        if self._catalogs is not None:
            return
        if self.files.is_materialized:
            return
        self.files.materialize_static_files(await publisher.materialize(self.files.sources))
