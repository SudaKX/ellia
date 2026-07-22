import asyncio
from uuid import uuid4

import httpx
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.endpoints import EffectAction, FollowupAction, PendingEffectPlan, RejectAction, ResponseAction
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.modules import ModuleRegistry


def test_framework_endpoints_execute_and_deduplicate(tmp_path) -> None:
    async def scenario() -> None:
        started = asyncio.Event()
        release = asyncio.Event()
        calls = {"checkpoint": 0, "retry": 0}
        catalog = ModuleRegistry()

        async def checkpoint_callback(context, payload):
            calls["checkpoint"] += 1
            checkpoint = payload["checkpoint"]
            plan = PendingEffectPlan().add(context.player.progress.set_checkpoint(checkpoint))
            return (
                EffectAction(plan),
                ResponseAction({"checkpoint": checkpoint}),
                FollowupAction({"event": "checkpoint-set"}),
            )

        async def retry_callback(context, _payload):
            calls["retry"] += 1
            plan = PendingEffectPlan().add(context.player.progress.set_checkpoint("retry"))
            if calls["retry"] == 1:
                return (EffectAction(plan), RejectAction(409, "retry command"))
            return (EffectAction(plan), ResponseAction({"checkpoint": "retry"}))

        async def waiting_callback(_context, _payload):
            started.set()
            await release.wait()
            return (ResponseAction({"finished": True}),)

        async def view_low(context):
            return (ResponseAction({"checkpoint": context.player.progress.checkpoint}),)

        async def view_high(context):
            return (ResponseAction({"version": context.player.progress.version}),)

        catalog.register_command("progress", "test.progress.checkpoint", checkpoint_callback)
        catalog.register_command("progress", "test.progress.retry", retry_callback)
        catalog.register_command("progress", "test.progress.wait", waiting_callback)
        catalog.register_view("dashboard", "test.dashboard.low", view_low, priority=10)
        catalog.register_view("dashboard", "test.dashboard.high", view_high, priority=1)

        database_path = tmp_path / "framework.sqlite3"
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, module_registry=catalog)

        async with app.router.lifespan_context(app):
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "framework-player", "password": "correct-horse-battery"},
                )
                token = registration.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}

                missing_request_id = await client.post(
                    "/api/v1/commands/progress",
                    headers=headers,
                    json={"stable_id": "test.progress.checkpoint", "payload": {"checkpoint": "first"}},
                )
                assert missing_request_id.status_code == 422

                request_id = str(uuid4())
                command_headers = {**headers, "Request-ID": request_id}
                payload = {"stable_id": "test.progress.checkpoint", "payload": {"checkpoint": "first"}}
                first = await client.post("/api/v1/commands/progress", headers=command_headers, json=payload)
                duplicate = await client.post("/api/v1/commands/progress", headers=command_headers, json=payload)
                assert first.status_code == duplicate.status_code == 200
                assert first.json() == duplicate.json()
                assert first.json() == {
                    "data": {"checkpoint": "first"},
                    "followups": [{"event": "checkpoint-set"}],
                    "state_revision": 2,
                }
                assert calls["checkpoint"] == 1

                other_registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "other-framework-player", "password": "correct-horse-battery"},
                )
                other_headers = {
                    "Authorization": f"Bearer {other_registration.json()['access_token']}",
                    "Request-ID": request_id,
                }
                cross_player_replay = await client.post(
                    "/api/v1/commands/progress",
                    headers=other_headers,
                    json=payload,
                )
                assert cross_player_replay.status_code == 409

                view = await client.get("/api/v1/views/dashboard", headers=headers)
                assert view.status_code == 200
                assert view.json() == {
                    "items": [
                        {"stable_id": "test.dashboard.high", "data": {"version": 2}},
                        {"stable_id": "test.dashboard.low", "data": {"checkpoint": "first"}},
                    ],
                    "followups": [],
                }

                retry_id = str(uuid4())
                retry_headers = {**headers, "Request-ID": retry_id}
                first_retry = await client.post(
                    "/api/v1/commands/progress",
                    headers=retry_headers,
                    json={"stable_id": "test.progress.retry", "payload": {}},
                )
                second_retry = await client.post(
                    "/api/v1/commands/progress",
                    headers=retry_headers,
                    json={"stable_id": "test.progress.retry", "payload": {}},
                )
                assert first_retry.status_code == 409
                assert second_retry.status_code == 200
                assert second_retry.json()["state_revision"] == 3
                assert calls["retry"] == 2

                wait_id = str(uuid4())
                wait_headers = {**headers, "Request-ID": wait_id}
                first_wait = asyncio.create_task(
                    client.post(
                        "/api/v1/commands/progress",
                        headers=wait_headers,
                        json={"stable_id": "test.progress.wait", "payload": {}},
                    )
                )
                await started.wait()
                in_progress = await client.post(
                    "/api/v1/commands/progress",
                    headers=wait_headers,
                    json={"stable_id": "test.progress.wait", "payload": {}},
                )
                assert in_progress.status_code == 409
                assert in_progress.headers["retry-after"] == "1"
                release.set()
                assert (await first_wait).status_code == 200

    asyncio.run(scenario())
