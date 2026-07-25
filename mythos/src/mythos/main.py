from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mythos.auth.router import router as auth_router
from mythos.core.config import Settings, get_settings
from mythos.core.database import Database
from mythos.core.file_ids import FileIdCodec
from mythos.core.runtime import ApplicationRuntime
from mythos.core.commands import CommandTransactionExecutor, RequestCache
from mythos.registry.bundle import RegistryBundle
from mythos.players.factory import PlayerFactory
from mythos.services.container import ServiceContainer
from mythos.services.object_store.service import create_object_store
from mythos.services.object_store.service import ObjectStore
from mythos.services.files.router import router as files_router
from mythos.services.scripts.router import router as scripts_router
from mythos.services.progress import LocalCheckpointStore, ProgressCheckpointHook
from mythos.services.validations.router import router as validations_router


def create_app(
    settings: Settings | None = None,
    registries: RegistryBundle | None = None,
    object_store: ObjectStore | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    registered_content = registries or RegistryBundle()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        file_ids = FileIdCodec(resolved_settings.file_id_secret)
        catalogs = registered_content.freeze(file_ids)
        resolved_object_store = object_store or create_object_store(resolved_settings)
        database = Database(resolved_settings.database_url)
        player_factory = PlayerFactory(catalogs)
        checkpoint_hook = ProgressCheckpointHook(
            LocalCheckpointStore(resolved_settings.checkpoint_directory)
        )
        command_executor = CommandTransactionExecutor(
            player_factory,
            RequestCache(
                maxsize=resolved_settings.request_cache_maxsize,
                ttl_seconds=resolved_settings.request_cache_ttl_seconds,
            ),
            (checkpoint_hook,),
        )
        application.state.settings = resolved_settings
        application.state.database = database
        application.state.runtime = ApplicationRuntime(
            catalogs=catalogs,
            player_factory=player_factory,
            services=ServiceContainer.create(
                catalogs.files,
                catalogs.scripts,
                catalogs.validations,
                resolved_object_store,
                resolved_settings.file_download_url_ttl_seconds,
            ),
            object_store=resolved_object_store,
            command_executor=command_executor,
        )
        try:
            yield
        finally:
            await database.dispose()

    application = FastAPI(
        title="Ellia Mythos API",
        version="0.1.0",
        lifespan=lifespan,
    )
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(files_router, prefix="/api/v1")
    application.include_router(scripts_router, prefix="/api/v1")
    application.include_router(validations_router, prefix="/api/v1")

    @application.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application

app = create_app()
