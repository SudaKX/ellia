import asyncio

import httpx
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import VirtualFile
from mythos.registry.scripts import Script


def test_global_services_read_frozen_registered_content(tmp_path) -> None:
    async def scenario() -> None:
        registries = RegistryBundle()
        registries.files.register(VirtualFile("test.readme", "/README.txt", "1", b"hello", "text/plain"))
        registries.scripts.register(Script("test.intro", "1", {"lines": ["hello"]}))
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'services.sqlite3').as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=registries)

        async with app.router.lifespan_context(app):
            first_services = app.state.runtime.services
            assert first_services is app.state.runtime.services
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "service-player", "password": "correct-horse-battery"},
                )
                headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
                assert (await client.get("/api/v1/files", headers=headers)).json() == {
                    "items": [{"stable_id": "test.readme", "path": "/README.txt", "revision": "1"}]
                }
                content = await client.get("/api/v1/files/test.readme", headers=headers)
                assert content.status_code == 200
                assert content.text == "hello"
                assert (await client.get("/api/v1/scripts", headers=headers)).json() == {
                    "items": [{"stable_id": "test.intro", "revision": "1", "body": {"lines": ["hello"]}}]
                }

    asyncio.run(scenario())
