import asyncio

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerProgress
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode


def test_registration_initializes_graph_entries(tmp_path) -> None:
    async def scenario() -> None:
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("intro.entry", (), is_entry=True))
        database_path = tmp_path / "progress.sqlite3"
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=registries)

        async with app.router.lifespan_context(app):
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "progress-player", "password": "correct-horse-battery"},
                )
                assert response.status_code == 201

            entry_id = app.state.runtime.catalogs.progress.node_ids_by_str_id["intro.entry"]
            async with app.state.database.session_factory() as session:
                progress = await session.scalar(select(PlayerProgress))
                assert progress is not None
                assert {item.node_id for item in progress.unlocked_nodes} == {entry_id}
                assert {item.node_id for item in progress.frontier_nodes} == {entry_id}
                assert progress.current_checkpoint_sequence == -1
                assert progress.next_checkpoint_sequence == 0

    asyncio.run(scenario())
