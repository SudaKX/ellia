import asyncio
from uuid import uuid4

import httpx
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode
from mythos.registry.validations import ValidationAttempt, ValidationResult


def test_progress_api_reads_and_restores_current_checkpoint(tmp_path) -> None:
    async def scenario() -> None:
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", ("saved",), is_entry=True))
        registries.progress.register(NormalProgressNode("saved", ("after",), triggers_checkpoint=True))
        registries.progress.register(NormalProgressNode("after", ()))

        async def save_handler(context, _payload):
            context.player.progress.push("saved")
            return ValidationResult(accepted=True)

        async def advance_handler(context, _payload):
            context.player.progress.push("after")
            return ValidationResult(accepted=True)

        registries.validations.register_attempt(ValidationAttempt("test.save", "save", save_handler))
        registries.validations.register_attempt(ValidationAttempt("test.advance", "advance", advance_handler))
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'progress.sqlite3').as_posix()}",
            checkpoint_directory=tmp_path / "checkpoints",
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
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "restore-player", "password": "correct-horse-battery"},
                )
                headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}
                save = await client.post(
                    "/api/v1/validations/save/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={},
                )
                assert save.status_code == 200
                advance = await client.post(
                    "/api/v1/validations/advance/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={},
                )
                assert advance.status_code == 200

                before_restore = await client.get("/api/v1/progress", headers=headers)
                assert before_restore.json()["frontier_nodes"] == ["after"]
                assert before_restore.json()["checkpoint_sequence"] == 0

                restored = await client.post(
                    "/api/v1/progress/checkpoints/restore",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert restored.status_code == 200
                assert restored.json()["content"]["progress"]["frontier_nodes"] == ["saved"]

                after_restore = await client.get("/api/v1/progress", headers=headers)
                assert after_restore.json()["frontier_nodes"] == ["saved"]

    asyncio.run(scenario())
