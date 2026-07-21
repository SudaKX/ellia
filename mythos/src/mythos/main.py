from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mythos.auth.router import router as auth_router
from mythos.core.config import Settings, get_settings
from mythos.core.database import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(resolved_settings.database_url)
        application.state.settings = resolved_settings
        application.state.database = database
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

    @application.get("/health", tags=["system"])
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    return application

app = create_app()
