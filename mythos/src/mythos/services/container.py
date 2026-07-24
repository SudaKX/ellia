from __future__ import annotations

from dataclasses import dataclass

from mythos.registry.files import FileTree
from mythos.registry.scripts import ScriptCatalog
from mythos.registry.validations import ValidationCatalog
from mythos.services.files.service import FileService
from mythos.services.object_store.service import ObjectStore
from mythos.services.scripts.service import ScriptService
from mythos.services.validations.service import ValidationService


@dataclass(frozen=True)
class ServiceContainer:
    files: FileService
    scripts: ScriptService
    validations: ValidationService

    @classmethod
    def create(
        cls,
        file_tree: FileTree,
        script_catalog: ScriptCatalog,
        validation_catalog: ValidationCatalog,
        object_store: ObjectStore,
        file_download_url_ttl_seconds: int,
    ) -> ServiceContainer:
        return cls(
            files=FileService(file_tree, object_store, file_download_url_ttl_seconds),
            scripts=ScriptService(script_catalog),
            validations=ValidationService(validation_catalog),
        )
