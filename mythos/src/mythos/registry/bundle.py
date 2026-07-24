from __future__ import annotations

from dataclasses import dataclass

from mythos.core.file_ids import FileIdCodec
from mythos.registry.files import FileRegistry, FileTree
from mythos.registry.scripts import ScriptCatalog, ScriptRegistry
from mythos.registry.validations import ValidationCatalog, ValidationRegistry


@dataclass(frozen=True)
class RuntimeCatalogs:
    files: FileTree
    scripts: ScriptCatalog
    validations: ValidationCatalog


class RegistryBundle:
    def __init__(self) -> None:
        self.files = FileRegistry()
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
            scripts=self.scripts.freeze(),
            validations=self.validations.freeze(),
        )
        return self._catalogs
