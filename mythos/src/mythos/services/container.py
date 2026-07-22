from __future__ import annotations

from dataclasses import dataclass

from mythos.registry.files import FileRegistry
from mythos.registry.scripts import ScriptRegistry
from mythos.services.files.service import FileService
from mythos.services.scripts.service import ScriptService


@dataclass(frozen=True)
class ServiceContainer:
    files: FileService
    scripts: ScriptService

    @classmethod
    def create(cls, file_registry: FileRegistry, script_registry: ScriptRegistry) -> ServiceContainer:
        return cls(files=FileService(file_registry), scripts=ScriptService(script_registry))
