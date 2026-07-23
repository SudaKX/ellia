from __future__ import annotations

from dataclasses import dataclass

from mythos.registry.files import FileCatalog
from mythos.registry.scripts import ScriptCatalog
from mythos.services.files.service import FileService
from mythos.services.scripts.service import ScriptService


@dataclass(frozen=True)
class ServiceContainer:
    files: FileService
    scripts: ScriptService

    @classmethod
    def create(cls, file_catalog: FileCatalog, script_catalog: ScriptCatalog) -> ServiceContainer:
        return cls(files=FileService(file_catalog), scripts=ScriptService(script_catalog))
