import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr

from _helpers.object_store import FakeObjectStore
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base


def test_credits_endpoint_tracks_committed_hint_spending(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'credits.sqlite3').as_posix()}",
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

        app = create_app(settings, object_store=FakeObjectStore())
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "credits-player", "password": "correct-horse-battery"},
                )
                token = registration.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                anonymous = await client.get("/api/v1/credits")
                assert anonymous.status_code == 401

                initial = await client.get("/api/v1/credits", headers=headers)
                assert initial.json() == {
                    "credits": [
                        {"credit_id": "example.moonstones", "balance": 5},
                        {"credit_id": "vtb", "balance": 5},
                    ],
                    "version": 2,
                }
                assert initial.headers["cache-control"] == "no-store"
                assert "Authorization" in initial.headers["vary"]

                hints = (await client.get("/api/v1/hints", headers=headers)).json()["hints"]
                for hint in sorted(hints, key=lambda item: item["credit_amount"]):
                    purchase = await client.post(
                        f"/api/v1/hints/{hint['hint_id']}/disclose",
                        headers={**headers, "Request-ID": str(uuid4())},
                    )
                    assert purchase.status_code == 200

                exhausted = await client.get("/api/v1/credits", headers=headers)
                assert exhausted.json() == {
                    "credits": [
                        {"credit_id": "example.moonstones", "balance": 5},
                        {"credit_id": "vtb", "balance": 5},
                    ],
                    "version": 5,
                }

                await client.post(
                    "/api/v1/vac/login",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"username": "guest", "password": "guest-echo-7"},
                )
                accepted = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"answer": "echo-7"},
                )
                assert accepted.json() == {"content": {"accepted": True}, "followups": []}

                gated = next(
                    hint
                    for hint in (await client.get("/api/v1/hints", headers=headers)).json()["hints"]
                    if hint["credit_amount"] == 5
                )
                gated_purchase = await client.post(
                    f"/api/v1/hints/{gated['hint_id']}/disclose",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert gated_purchase.status_code == 200
                assert (await client.get("/api/v1/credits", headers=headers)).json() == {
                    "credits": [
                        {"credit_id": "example.moonstones", "balance": 5},
                        {"credit_id": "vtb", "balance": 10},
                    ],
                    "version": 7,
                }

    asyncio.run(scenario())


def test_production_example_does_not_seed_vtb(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            environment="production",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'production-credits.sqlite3').as_posix()}",
            checkpoint_directory=tmp_path / "checkpoints",
            jwt_signing_key=SecretStr("production-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("production-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("production-file-id-signing-key-with-at-least-32-bytes"),
            problem_type_base_url="https://problems.test/ellia/problems",
            refresh_cookie_secure=True,
            object_store_endpoint="https://objects.test",
            object_store_bucket="production-test-bucket",
            object_store_access_key=SecretStr("production-test-access-key"),
            object_store_secret_key=SecretStr("production-test-secret-key"),
            object_store_use_tls=True,
        )
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()

        app = create_app(settings, object_store=FakeObjectStore())
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "production-player", "password": "correct-horse-battery"},
                )
                headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
                credits = await client.get("/api/v1/credits", headers=headers)
                assert credits.status_code == 200
                assert credits.json() == {
                    "credits": [
                        {"credit_id": "example.moonstones", "balance": 5},
                        {"credit_id": "vtb", "balance": 0},
                    ],
                    "version": 1,
                }

    asyncio.run(scenario())
