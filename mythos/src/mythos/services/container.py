from __future__ import annotations

from dataclasses import dataclass

from mythos.core.file_ids import FileIdCodec
from mythos.registry.files import FileTree
from mythos.registry.hints import HintCatalog
from mythos.registry.progress import ProgressGraph
from mythos.registry.scripts import ScriptCatalog
from mythos.registry.validations import ValidationCatalog
from mythos.services.accounts.service import AccountService
from mythos.services.files.service import FileService
from mythos.services.hints.service import HintService
from mythos.services.object_store.service import ObjectStoreReader
from mythos.services.progress.checkpoint_store import LocalCheckpointStore
from mythos.services.progress.service import ProgressService
from mythos.services.scripts.service import ScriptService
from mythos.services.validations.service import ValidationService


@dataclass(frozen=True)
class ServiceContainer:
    accounts: AccountService
    files: FileService
    hints: HintService
    progress: ProgressService
    scripts: ScriptService
    validations: ValidationService

    @classmethod
    def create(
        cls,
        file_tree: FileTree,
        hint_catalog: HintCatalog,
        progress_graph: ProgressGraph,
        script_catalog: ScriptCatalog,
        validation_catalog: ValidationCatalog,
        object_store: ObjectStoreReader,
        file_content_url_ttl_seconds: int,
        file_content_cache_max_age_seconds: int,
        file_download_url_ttl_seconds: int,
        checkpoint_store: LocalCheckpointStore,
        file_ids: FileIdCodec,
    ) -> ServiceContainer:
        return cls(
            accounts=AccountService(),
            files=FileService(
                file_tree,
                object_store,
                file_content_url_ttl_seconds,
                file_content_cache_max_age_seconds,
                file_download_url_ttl_seconds,
                file_ids,
            ),
            hints=HintService(
                hint_catalog,
                object_store,
                file_content_url_ttl_seconds,
                file_content_cache_max_age_seconds,
            ),
            progress=ProgressService(progress_graph, checkpoint_store),
            scripts=ScriptService(script_catalog),
            validations=ValidationService(validation_catalog),
        )
