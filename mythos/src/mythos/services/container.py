from __future__ import annotations

from dataclasses import dataclass

from mythos.registry.files import FileTree
from mythos.registry.scripts import ScriptCatalog
from mythos.services.files.service import FileService
from mythos.services.object_store.service import ObjectStore
from mythos.services.scripts.service import ScriptService


@dataclass(frozen=True)
class ServiceContainer:
    files: FileService
    scripts: ScriptService

    @classmethod
    def create(
        cls,
        file_tree: FileTree,
        script_catalog: ScriptCatalog,
        object_store: ObjectStore,
        file_download_url_ttl_seconds: int,
    ) -> ServiceContainer:
        return cls(
            files=FileService(file_tree, object_store, file_download_url_ttl_seconds),
            scripts=ScriptService(script_catalog),
        )
