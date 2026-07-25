import asyncio
from uuid import uuid4

import httpx
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode
from mythos.registry.validations import ValidationAttempt, ValidationOutcome


def test_validation_attempts_execute_and_deduplicate(tmp_path) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        calls = {"checkpoint": 0, "retry": 0}
        retry_versions: list[int] = []
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", ("checkpoint",), is_entry=True))
        registries.progress.register(NormalProgressNode("checkpoint", ("retry",)))
        registries.progress.register(NormalProgressNode("retry", ()))

        async def checkpoint_handler(context, payload):
            calls["checkpoint"] += 1
            checkpoint = payload["checkpoint"]
            context.player.progress.push("checkpoint")
            context.follow({"event": "checkpoint-set"})
            return ValidationOutcome(accepted=True, checkpoint=checkpoint)

        async def retry_handler(context, _payload):
            calls["retry"] += 1
            context.player.progress.push("retry")
            if calls["retry"] == 1:
                context.reject(409, "retry command")
            retry_versions.append(context.player.progress.version)
            return ValidationOutcome(accepted=True, checkpoint="retry")

        async def waiting_handler(_context, _payload):
            started.set()
            await release.wait()
            return ValidationOutcome(accepted=True, checkpoint=None)

        registries.validations.register_attempt(
            ValidationAttempt("test.validation.checkpoint", "checkpoint", checkpoint_handler)
        )
        registries.validations.register_attempt(
            ValidationAttempt("test.validation.retry", "retry", retry_handler)
        )
        registries.validations.register_attempt(
            ValidationAttempt("test.validation.wait", "wait", waiting_handler)
        )

        database_path = tmp_path / "validation.sqlite3"
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
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "validation-player", "password": "correct-horse-battery"},
                )
                token = registration.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                missing_request_id = await client.post(
                    "/api/v1/validations/checkpoint/attempts",
                    headers=headers,
                    json={"checkpoint": "first"},
                )
                assert missing_request_id.status_code == 422

                request_id = str(uuid4())
                command_headers = {**headers, "Request-ID": request_id}
                first = await client.post(
                    "/api/v1/validations/checkpoint/attempts",
                    headers=command_headers,
                    json={"checkpoint": "first"},
                )
                duplicate = await client.post(
                    "/api/v1/validations/checkpoint/attempts",
                    headers=command_headers,
                    json={"checkpoint": "first"},
                )
                assert first.status_code == duplicate.status_code == 200
                assert first.json() == duplicate.json() == {
                    "content": {"accepted": True, "checkpoint": "first"},
                    "followups": [{"event": "checkpoint-set"}],
                }
                assert calls["checkpoint"] == 1

                removed_generic_endpoint = await client.post(
                    "/api/v1/commands/progress",
                    headers=command_headers,
                    json={"stable_id": "test.validation.checkpoint", "payload": {"checkpoint": "ignored"}},
                )
                assert removed_generic_endpoint.status_code == 404
                removed_generic_view = await client.get("/api/v1/views/dashboard", headers=headers)
                assert removed_generic_view.status_code == 404

                other_registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "other-validation-player", "password": "correct-horse-battery"},
                )
                other_headers = {
                    "Authorization": f"Bearer {other_registration.json()['access_token']}",
                    "Request-ID": request_id,
                }
                cross_player_replay = await client.post(
                    "/api/v1/validations/checkpoint/attempts",
                    headers=other_headers,
                    json={"checkpoint": "first"},
                )
                assert cross_player_replay.status_code == 409

                retry_id = str(uuid4())
                retry_headers = {**headers, "Request-ID": retry_id}
                first_retry = await client.post(
                    "/api/v1/validations/retry/attempts",
                    headers=retry_headers,
                    json={},
                )
                second_retry = await client.post(
                    "/api/v1/validations/retry/attempts",
                    headers=retry_headers,
                    json={},
                )
                assert first_retry.status_code == 409
                assert second_retry.status_code == 200
                assert second_retry.json()["content"] == {"accepted": True, "checkpoint": "retry"}
                assert calls["retry"] == 2
                assert retry_versions == [3]

                wait_id = str(uuid4())
                wait_headers = {**headers, "Request-ID": wait_id}
                first_wait = asyncio.create_task(
                    client.post(
                        "/api/v1/validations/wait/attempts",
                        headers=wait_headers,
                        json={},
                    )
                )
                await started.wait()
                in_progress = await client.post(
                    "/api/v1/validations/wait/attempts",
                    headers=wait_headers,
                    json={},
                )
                assert in_progress.status_code == 409
                assert in_progress.headers["retry-after"] == "1"
                release.set()
                assert (await first_wait).status_code == 200

    asyncio.run(scenario())
