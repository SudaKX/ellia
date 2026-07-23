from __future__ import annotations

from dataclasses import dataclass

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

    def freeze(self) -> RuntimeCatalogs:
        if self._catalogs is not None:
            return self._catalogs
        self._catalogs = RuntimeCatalogs(
            modules=self.modules.freeze(),
            files=self.files.freeze(),
            scripts=self.scripts.freeze(),
        )
        return self._catalogs
