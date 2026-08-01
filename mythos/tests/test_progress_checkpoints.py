import asyncio
import json
from uuid import uuid4

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerProgress, PlayerProgressCheckpoint
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode
from mythos.registry.validations import ValidationAttempt, ValidationOutcome


def test_checkpoint_hook_persists_stable_progress_snapshot(tmp_path) -> None:
    async def scenario() -> None:
        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", ("saved",), is_entry=True))
        registries.progress.register(NormalProgressNode("saved", (), triggers_checkpoint=True))

        async def handler(context, _payload):
            context.player.progress.push("saved")
            return ValidationOutcome(accepted=True)

        registries.validations.register_attempt(ValidationAttempt("test.save", "save", handler))
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
                    json={"username": "checkpoint-player", "password": "correct-horse-battery"},
                )
                headers = {
                    "Authorization": f"Bearer {registration.json()['access_token']}",
                    "Request-ID": str(uuid4()),
                }
                response = await client.post("/api/v1/validations/save/attempts", headers=headers, json={})
                assert response.status_code == 200

            async with app.state.database.session_factory() as session:
                progress = await session.scalar(select(PlayerProgress))
                checkpoint = await session.scalar(select(PlayerProgressCheckpoint))
                assert progress is not None
                assert checkpoint is not None
                assert progress.current_checkpoint_sequence == 0
                assert progress.next_checkpoint_sequence == 1

            snapshot = json.loads((settings.checkpoint_directory / checkpoint.storage_key).read_text())
            saved_id = app.state.runtime.catalogs.progress.node_ids_by_str_id["saved"]
            assert snapshot["sequence"] == 0
            assert snapshot["graph_hash"] == app.state.runtime.catalogs.progress.structure_hash
            assert snapshot["frontier_node_ids"] == [saved_id]

    asyncio.run(scenario())
