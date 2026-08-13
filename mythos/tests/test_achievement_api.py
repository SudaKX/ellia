from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr

from _helpers.object_store import FakeObjectStore
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.core.file_ids import FileIdCodec
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.achievements import AchievementDefinition
from mythos.registry.bundle import RegistryBundle
from mythos.registry.callbacks import module_handler
from mythos.players.interfaces import PlayerInterfaces


def test_achievement_http_api_query_check_claim_and_replay(tmp_path: Path) -> None:
    async def scenario() -> None:
        effects: list[str] = []

        @module_handler("test.api")(1, dependencies=PlayerInterfaces.NONE)
        def condition(_player) -> bool:
            return True

        @module_handler("test.api")(2, dependencies=PlayerInterfaces.NONE)
        async def effect(_player) -> None:
            effects.append("effect")

        registries = RegistryBundle()
        registries.achievements.register(
            AchievementDefinition("test.api-achievement", False, {"title": "API"}, condition, effect)
        )
        database_path = tmp_path / "achievement-api.sqlite3"
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
            checkpoint_directory=tmp_path / "checkpoints",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()

        app = create_app(settings, registries=registries, object_store=FakeObjectStore())
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                anonymous = await client.get("/api/v1/achievement")
                assert anonymous.status_code == 401

                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "achievement-api", "password": "correct-horse-battery"},
                )
                assert registration.status_code == 201
                headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

                initial = await client.get("/api/v1/achievement", headers=headers)
                assert initial.status_code == 200
                assert initial.headers["cache-control"] == "no-store"
                item = initial.json()["items"][0]
                assert item["status"] == "locked"
                assert item["meta"] == {"title": "API"}

                check_id = uuid4()
                checked = await client.post(
                    "/api/v1/achievement/check",
                    headers={**headers, "Request-ID": str(check_id)},
                )
                assert checked.status_code == 200
                assert checked.json()["content"]["check"]["earned"] == [item["public_id"]]
                assert effects == []

                claim_id = uuid4()
                claimed = await client.post(
                    f"/api/v1/achievement/claim/{item['public_id']}",
                    headers={**headers, "Request-ID": str(claim_id)},
                )
                replay = await client.post(
                    f"/api/v1/achievement/claim/{item['public_id']}",
                    headers={**headers, "Request-ID": str(claim_id)},
                )
                assert claimed.status_code == 200
                assert claimed.json()["content"]["achievement"]["status"] == "claimed"
                assert replay.json() == claimed.json()
                assert effects == ["effect"]

                repeated = await client.post(
                    f"/api/v1/achievement/claim/{item['public_id']}",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert repeated.status_code == 200
                assert effects == ["effect"]

                missing_request_id = await client.post("/api/v1/achievement/check", headers=headers)
                assert missing_request_id.status_code == 422
                assert missing_request_id.headers["content-type"].startswith("application/problem+json")

    asyncio.run(scenario())
