from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mythos.auth.router import router as auth_router
from mythos.core.config import Settings, get_settings
from mythos.core.database import Database
from mythos.endpoints.cache import RequestCache
from mythos.endpoints.dispatcher import EndpointDispatcher
from mythos.endpoints.router import router as endpoint_router
from mythos.registry.files import FileRegistry
from mythos.registry.modules import ModuleRegistry, build_module_registry
from mythos.registry.scripts import ScriptRegistry
from mythos.services.container import ServiceContainer
from mythos.services.files.router import router as files_router
from mythos.services.scripts.router import router as scripts_router


def create_app(
    settings: Settings | None = None,
    module_registry: ModuleRegistry | None = None,
    file_registry: FileRegistry | None = None,
    script_registry: ScriptRegistry | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    modules = module_registry or build_module_registry()
    files = file_registry or FileRegistry()
    scripts = script_registry or ScriptRegistry()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(resolved_settings.database_url)
        modules.freeze()
        files.freeze()
        scripts.freeze()
        application.state.settings = resolved_settings
        application.state.database = database
        application.state.module_registry = modules
        application.state.services = ServiceContainer.create(files, scripts)
        application.state.endpoint_dispatcher = EndpointDispatcher(
            modules,
            RequestCache(
                maxsize=resolved_settings.request_cache_maxsize,
                ttl_seconds=resolved_settings.request_cache_ttl_seconds,
            ),
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
    application.include_router(endpoint_router, prefix="/api/v1")
    application.include_router(files_router, prefix="/api/v1")
    application.include_router(scripts_router, prefix="/api/v1")

    @application.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application

app = create_app()
