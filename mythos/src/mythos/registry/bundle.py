from __future__ import annotations

from dataclasses import dataclass

from mythos.core.file_ids import FileIdCodec
from mythos.registry.files import FileCatalog, FileRegistry
from mythos.registry.modules import ModuleCatalog, ModuleRegistry
from mythos.registry.scripts import ScriptCatalog, ScriptRegistry


@dataclass(frozen=True)
class RuntimeCatalogs:
    modules: ModuleCatalog
    files: FileCatalog
    scripts: ScriptCatalog


class RegistryBundle:
    def __init__(self) -> None:
        self.modules = ModuleRegistry()
        self.files = FileRegistry()
        self.scripts = ScriptRegistry()
        self._catalogs: RuntimeCatalogs | None = None

    def freeze(self, file_ids: FileIdCodec) -> RuntimeCatalogs:
        if self._catalogs is not None:
            if self._catalogs.files.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RuntimeError("RegistryBundle is already frozen with a different file ID key.")
            return self._catalogs
        self._catalogs = RuntimeCatalogs(
            modules=self.modules.freeze(),
            files=self.files.freeze(file_ids),
            scripts=self.scripts.freeze(),
        )
        return self._catalogs
