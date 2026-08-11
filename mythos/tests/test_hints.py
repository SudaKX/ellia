import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr
from sqlalchemy import func, select

from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerCredits, PlayerHintDisclosure
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileReference
from mythos.registry.hints import Hint, HintDisplayParams
from mythos.registry.progress import NormalProgressNode


def test_hints_disclose_static_content_with_atomic_vtb_spending(tmp_path: Path) -> None:
    async def scenario() -> None:
        puzzle_root = tmp_path / "puzzles"
        source_path = puzzle_root / "test" / "assets" / "hint.txt"
        source_path.parent.mkdir(parents=True)
        source_path.write_text("The answer is Echo-7.", encoding="utf-8")
        source = FileReference("test", "assets/hint.txt", "text/plain; charset=utf-8")

        registries = RegistryBundle()
        registries.progress.register(NormalProgressNode("start", (), is_entry=True))
        for stable_id, title in (("test.hint.one", "First hint"), ("test.hint.two", "Second hint")):
            registries.hints.register(
                Hint(
                    stable_id=stable_id,
                    source=source,
                    download_name="hint.txt",
                    display=HintDisplayParams(title=title, teaser="A small clue", icon="hint"),
                    vtb_cost=3,
                )
            )

        @registries.lifecycle.on_construct
        async def grant_initial_vtb(context) -> None:
            await context.player.credits.grant_vtb(3)

        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'hints.sqlite3').as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
            puzzle_root=puzzle_root,
            file_content_url_ttl_seconds=60,
            file_content_cache_max_age_seconds=55,
        )
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()

        object_store = FakeObjectStore()
        app = create_app(settings, registries=registries, object_store=object_store)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                first_token = await _register(client, "first-hint-player")
                first_headers = {"Authorization": f"Bearer {first_token}"}
                listing = await client.get("/api/v1/hints", headers=first_headers)
                assert listing.status_code == 200
                assert listing.headers["cache-control"] == "no-store"
                assert "vtb" not in listing.json()
                first_hint, second_hint = listing.json()["hints"]
                assert first_hint["hint_id"].startswith("h1_")
                assert first_hint["display"] == {
                    "title": "First hint",
                    "teaser": "A small clue",
                    "icon": "hint",
                    "sort_order": 0,
                }
                assert "content_token" not in first_hint

                first_purchase, second_purchase = await asyncio.gather(
                    client.post(
                        f"/api/v1/hints/{first_hint['hint_id']}/disclose",
                        headers={**first_headers, "Request-ID": str(uuid4())},
                    ),
                    client.post(
                        f"/api/v1/hints/{second_hint['hint_id']}/disclose",
                        headers={**first_headers, "Request-ID": str(uuid4())},
                    ),
                )
                assert sorted((first_purchase.status_code, second_purchase.status_code)) == [200, 409]

                first_player_id = decode_access_token(first_token, settings).player_id
                async with app.state.database.session_factory() as session:
                    credits = await session.get(PlayerCredits, first_player_id)
                    assert credits is not None and credits.vtb == 0
                    disclosures = await session.scalar(
                        select(func.count()).select_from(PlayerHintDisclosure).where(
                            PlayerHintDisclosure.player_id == first_player_id
                        )
                    )
                    assert disclosures == 1

                second_token = await _register(client, "second-hint-player")
                second_headers = {"Authorization": f"Bearer {second_token}"}
                second_listing = await client.get("/api/v1/hints", headers=second_headers)
                hint_id = second_listing.json()["hints"][0]["hint_id"]
                first_claim, repeated_claim = await asyncio.gather(
                    client.post(
                        f"/api/v1/hints/{hint_id}/disclose",
                        headers={**second_headers, "Request-ID": str(uuid4())},
                    ),
                    client.post(
                        f"/api/v1/hints/{hint_id}/disclose",
                        headers={**second_headers, "Request-ID": str(uuid4())},
                    ),
                )
                assert first_claim.status_code == repeated_claim.status_code == 200
                content_token = first_claim.json()["content"]["hint"]["content_token"]
                assert content_token.startswith("hv1_")

                second_player_id = decode_access_token(second_token, settings).player_id
                async with app.state.database.session_factory() as session:
                    credits = await session.get(PlayerCredits, second_player_id)
                    assert credits is not None and credits.vtb == 0
                    disclosures = await session.scalar(
                        select(func.count()).select_from(PlayerHintDisclosure).where(
                            PlayerHintDisclosure.player_id == second_player_id
                        )
                    )
                    assert disclosures == 1

                content_url = await client.get(
                    f"/api/v1/hints/{hint_id}/{content_token}/content-url",
                    headers=second_headers,
                )
                assert content_url.status_code == 200
                assert content_url.headers["etag"] == f'"{content_token}"'
                assert content_url.json()["url"] == "https://objects.test/static/test/assets/hint.txt?expires=60"
                assert object_store.upload_keys == ["static/test/assets/hint.txt"]

                third_token = await _register(client, "third-hint-player")
                undisclosed_url = await client.get(
                    f"/api/v1/hints/{hint_id}/{content_token}/content-url",
                    headers={"Authorization": f"Bearer {third_token}"},
                )
                assert undisclosed_url.status_code == 403

    asyncio.run(scenario())


async def _register(client: httpx.AsyncClient, username: str) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": "correct-horse-battery"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]
