from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from mythos.auth.router import router as auth_router
from mythos.services.accounts.router import router as accounts_router
from mythos.core.config import PROJECT_ROOT, Settings, get_settings
from mythos.core.database import Database
from mythos.core.file_ids import FileIdCodec
from mythos.core.runtime import ApplicationRuntime
from mythos.core.commands import CommandTransactionExecutor, RequestCache
from mythos.puzzles import register_all
from mythos.registry.bundle import RegistryBundle
from mythos.players.factory import PlayerFactory
from mythos.services.container import ServiceContainer
from mythos.services.object_store.service import create_object_store
from mythos.services.object_store.service import ObjectStore
from mythos.services.files.router import router as files_router
from mythos.services.hints.router import router as hints_router
from mythos.services.credits.router import router as credits_router
from mythos.services.scripts.router import router as scripts_router
from mythos.services.progress import LocalCheckpointStore, ProgressCheckpointHook
from mythos.services.progress.router import router as progress_router
from mythos.services.validations.router import router as validations_router
from mythos.services.files.static_assets import StaticAssetPublisher
from mythos.services.artifacts.reconciliation import ArtifactReconciliationRunner
from mythos.services.artifacts.snapshot import ArtifactTemplateSnapshotStore
from mythos.services.accounts.reconciliation import AccountReconciliationRunner
from mythos.services.accounts.snapshot import VirtualAccountTemplateSnapshotStore
from mythos.services.lifecycle import PlayerLifecycleDispatcher
from mythos.core.problems import (
    ApiProblem,
    PROBLEM_MEDIA_TYPE,
    PROBLEM_STATUS_CODES,
    ProblemDetails,
    api_problem_handler,
    http_exception_handler,
    request_validation_exception_handler,
    unhandled_exception_handler,
)


def create_app(
    settings: Settings | None = None,
    registries: RegistryBundle | None = None,
    object_store: ObjectStore | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    if registries is None:
        registered_content = RegistryBundle(resolved_settings.puzzle_root)
        register_all(
            registered_content,
            example_initial_vtb=5 if resolved_settings.environment in {"development", "test"} else 0,
        )
    else:
        registered_content = registries
    registered_content.configure_puzzle_root(resolved_settings.puzzle_root)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        file_ids = FileIdCodec(resolved_settings.file_id_secret)
        resolved_object_store = object_store or create_object_store(resolved_settings)
        database = Database(resolved_settings.database_url)
        await registered_content.materialize_static_files(
            StaticAssetPublisher(
                database.session_factory,
                resolved_object_store,
                resolved_settings.puzzle_root,
            )
        )
        catalogs = registered_content.freeze(file_ids)
        player_factory = PlayerFactory(catalogs, resolved_object_store, file_ids)
        checkpoint_store = LocalCheckpointStore(resolved_settings.checkpoint_directory)
        checkpoint_hook = ProgressCheckpointHook(checkpoint_store)
        command_executor = CommandTransactionExecutor(
            player_factory,
            RequestCache(
                maxsize=resolved_settings.request_cache_maxsize,
                ttl_seconds=resolved_settings.request_cache_ttl_seconds,
            ),
            (checkpoint_hook,),
        )
        lifecycle_dispatcher = PlayerLifecycleDispatcher(catalogs.lifecycle)
        await ArtifactReconciliationRunner(
            database.session_factory,
            command_executor,
            catalogs.artifacts,
            ArtifactTemplateSnapshotStore(resolved_settings.artifact_snapshot_path),
            allow_missing_tables=resolved_settings.environment == "test",
        ).run()
        await AccountReconciliationRunner(
            database.session_factory,
            command_executor,
            catalogs.accounts,
            VirtualAccountTemplateSnapshotStore(resolved_settings.virtual_account_snapshot_path),
            allow_empty_catalog=resolved_settings.allow_empty_virtual_account_catalog_reconciliation,
            allow_missing_tables=resolved_settings.environment == "test",
        ).run()
        application.state.settings = resolved_settings
        application.state.database = database
        application.state.runtime = ApplicationRuntime(
            catalogs=catalogs,
            player_factory=player_factory,
            services=ServiceContainer.create(
                catalogs.files,
                catalogs.hints,
                catalogs.progress,
                catalogs.scripts,
                catalogs.validations,
                resolved_object_store,
                resolved_settings.file_content_url_ttl_seconds,
                resolved_settings.file_content_cache_max_age_seconds,
                resolved_settings.file_download_url_ttl_seconds,
                checkpoint_store,
                file_ids,
            ),
            object_store=resolved_object_store,
            command_executor=command_executor,
            lifecycle_dispatcher=lifecycle_dispatcher,
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
    application.state.settings = resolved_settings
    application.add_exception_handler(ApiProblem, api_problem_handler)
    application.add_exception_handler(StarletteHTTPException, http_exception_handler)
    application.add_exception_handler(RequestValidationError, request_validation_exception_handler)
    application.add_exception_handler(Exception, unhandled_exception_handler)
    application.openapi = lambda: _openapi_with_problem_details(application)
    if resolved_settings.environment == "development":
        application.mount(
            "/example",
            StaticFiles(directory=PROJECT_ROOT / "example", html=True),
            name="example",
        )
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(accounts_router, prefix="/api/v1")
    application.include_router(files_router, prefix="/api/v1")
    application.include_router(hints_router, prefix="/api/v1")
    application.include_router(credits_router, prefix="/api/v1")
    application.include_router(progress_router, prefix="/api/v1")
    application.include_router(scripts_router, prefix="/api/v1")
    application.include_router(validations_router, prefix="/api/v1")

    @application.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application

app = create_app()


def _openapi_with_problem_details(application: FastAPI) -> dict[str, object]:
    if application.openapi_schema is not None:
        return application.openapi_schema
    schema = get_openapi(
        title=application.title,
        version=application.version,
        routes=application.routes,
    )
    components = schema.setdefault("components", {}).setdefault("schemas", {})
    components["ProblemDetails"] = ProblemDetails.model_json_schema()
    problem_response = {
        "description": "RFC 9457 Problem Details response.",
        "content": {
            PROBLEM_MEDIA_TYPE: {
                "schema": {"$ref": "#/components/schemas/ProblemDetails"},
            }
        },
    }
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.setdefault("responses", {})
            for status_code in PROBLEM_STATUS_CODES:
                responses[str(status_code)] = problem_response
    application.openapi_schema = schema
    return schema
