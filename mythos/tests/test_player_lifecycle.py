import asyncio
from pathlib import Path

import httpx
from pydantic import SecretStr
from sqlalchemy import select, update

from mythos.core.config import Settings
from mythos.core.problems import ProblemType
from mythos.core.database import Database
from mythos.eventbus import EventContext, PlayerConstructedEvent
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerProgress, PlayerProgressCheckpoint, PlayerRecord, PlayerVirtualAccount
from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.accounts import VirtualAccountTemplate
from mythos.registry.bundle import RegistryBundle
from mythos.registry.callbacks import module_handler
from mythos.registry.progress import NormalProgressNode


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'lifecycle.sqlite3').as_posix()}",
        checkpoint_directory=tmp_path / "checkpoints",
        jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
        refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
        file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
        refresh_cookie_secure=False,
    )


def _registries(events: list[PlayerConstructedEvent], *, advance_progress: bool = False) -> RegistryBundle:
    registries = RegistryBundle()
    registries.accounts.register_template(VirtualAccountTemplate("test.guest", "Guest", permission=1))
    if advance_progress:
        registries.progress.register(NormalProgressNode("start", ("complete",), is_entry=True))
        registries.progress.register(NormalProgressNode("complete", (), triggers_checkpoint=True))

    @registries.events.on(PlayerConstructedEvent)
    @module_handler("test.lifecycle")(1, dependencies=PlayerInterfaces.ALL)
    async def _construct(context: EventContext) -> None:
        assert isinstance(context.event, PlayerConstructedEvent)
        events.append(context.event)
        await context.player.accounts.issue("test.guest", "guest", "guest-password")
        if advance_progress:
            context.player.progress.push("complete")

    return registries


def test_registration_constructs_once_and_runs_pre_commit_hooks(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path)
        events: list[PlayerConstructedEvent] = []
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()
        app = create_app(settings, registries=_registries(events, advance_progress=True))

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "constructed-player", "password": "correct-horse-battery"},
                )
                assert registered.status_code == 201
                logged_in = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "constructed-player", "password": "correct-horse-battery"},
                )
                assert logged_in.status_code == 200

            assert [event.trigger for event in events] == ["registration"]
            async with app.state.database.session_factory() as session:
                player = await session.scalar(select(PlayerRecord))
                assert player is not None
                assert player.constructed_at is not None
                account = await session.get(PlayerVirtualAccount, (player.id, "test.guest"))
                assert account is not None
                progress = await session.get(PlayerProgress, player.id)
                assert progress is not None
                assert progress.current_checkpoint_sequence == 0
                checkpoint = await session.get(PlayerProgressCheckpoint, (player.id, 0))
                assert checkpoint is not None

    asyncio.run(scenario())


def test_first_login_constructs_a_legacy_player_without_a_marker(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path)
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()

        legacy = create_app(settings, registries=RegistryBundle())
        async with legacy.router.lifespan_context(legacy):
            transport = httpx.ASGITransport(app=legacy)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "legacy-player", "password": "correct-horse-battery"},
                )
                assert registered.status_code == 201

        async with legacy.state.database.session_factory() as session:
            async with session.begin():
                await session.execute(update(PlayerRecord).values(constructed_at=None))

        events: list[PlayerConstructedEvent] = []
        upgraded = create_app(settings, registries=_registries(events))
        async with upgraded.router.lifespan_context(upgraded):
            transport = httpx.ASGITransport(app=upgraded)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                logged_in = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "legacy-player", "password": "correct-horse-battery"},
                )
                assert logged_in.status_code == 200

            assert [event.trigger for event in events] == ["first_login"]
            async with upgraded.state.database.session_factory() as session:
                player = await session.scalar(select(PlayerRecord))
                assert player is not None
                assert player.constructed_at is not None
                assert await session.get(PlayerVirtualAccount, (player.id, "test.guest")) is not None

    asyncio.run(scenario())


def test_failed_construct_rolls_back_registration(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path)
        registries = RegistryBundle()

        @registries.events.on(PlayerConstructedEvent)
        @module_handler("test.lifecycle")(2, dependencies=PlayerInterfaces.NONE)
        async def _fail(_context: EventContext) -> None:
            raise RuntimeError("construction failed")

        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()
        app = create_app(settings, registries=registries)

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "failed-player", "password": "correct-horse-battery"},
                )
                assert response.status_code == 500
                assert response.headers["content-type"].startswith("application/problem+json")
                assert response.json()["type"] == settings.problem_type_url(ProblemType.INTERNAL_ERROR)

            async with app.state.database.session_factory() as session:
                assert await session.scalar(select(PlayerRecord)) is None

    asyncio.run(scenario())
