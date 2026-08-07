import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr

from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base


def test_example_module_runs_guest_to_administrator_flow(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'example.sqlite3').as_posix()}",
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

        object_store = FakeObjectStore()
        app = create_app(settings, object_store=object_store)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "example-player", "password": "correct-horse-battery"},
                )
                assert registration.status_code == 201
                access_token = registration.json()["access_token"]
                headers = {"Authorization": f"Bearer {access_token}"}
                player_id = decode_access_token(access_token, settings).player_id

                initial_credits = await client.get("/api/v1/credits", headers=headers)
                assert initial_credits.status_code == 200
                assert initial_credits.json()["vtb"] == 5
                assert initial_credits.json()["version"] == 1
                assert initial_credits.headers["cache-control"] == "no-store"
                assert "Authorization" in initial_credits.headers["vary"]

                initial_hints = await client.get("/api/v1/hints", headers=headers)
                assert initial_hints.status_code == 200
                public_hints = initial_hints.json()["hints"]
                assert len(public_hints) == 2
                assert sorted(hint["vtb_cost"] for hint in public_hints) == [2, 3]
                assert all(not hint["disclosed"] and "content_token" not in hint for hint in public_hints)
                purchased_hint = next(hint for hint in public_hints if hint["vtb_cost"] == 2)
                purchase = await client.post(
                    f"/api/v1/hints/{purchased_hint['hint_id']}/disclose",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert purchase.status_code == 200
                purchased_content_token = purchase.json()["content"]["hint"]["content_token"]
                assert purchased_content_token.startswith("hv1_")

                repeated_purchase = await client.post(
                    f"/api/v1/hints/{purchased_hint['hint_id']}/disclose",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert repeated_purchase.status_code == 200
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 3

                hint_content_url = await client.get(
                    f"/api/v1/hints/{purchased_hint['hint_id']}/{purchased_content_token}/content-url",
                    headers=headers,
                )
                assert hint_content_url.status_code == 200
                assert hint_content_url.json()["url"] == (
                    "https://objects.test/static/example/assets/hints/echo-clue.txt?expires=43200"
                )
                assert "线索一".encode() in object_store.objects["static/example/assets/hints/echo-clue.txt"]

                initial_progress = await client.get("/api/v1/progress", headers=headers)
                assert initial_progress.json()["unlocked_nodes"] == ["example.entry"]
                initial_tree = await client.get("/api/v1/files/tree", headers=headers)
                assert [directory["path"] for directory in initial_tree.json()["directories"]] == ["/public"]
                assert (await client.get("/api/v1/files/ls", params={"path": "/admin"}, headers=headers)).status_code == 404
                assert (await client.get("/api/v1/scripts", headers=headers)).json() == {"items": []}

                rejected_before_guest_login = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"answer": "echo-7"},
                )
                assert rejected_before_guest_login.json() == {"content": {"accepted": False}, "followups": []}

                guest_login = await client.post(
                    "/api/v1/vac/login",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"username": "guest", "password": "guest-echo-7"},
                )
                assert guest_login.status_code == 200
                assert guest_login.json()["content"]["current_account"]["account_id"] == "example.guest"

                guest_scripts = await client.get("/api/v1/scripts", headers=headers)
                assert [item["stable_id"] for item in guest_scripts.json()["items"]] == ["example.boot"]

                completed, repeated = await asyncio.gather(
                    client.post(
                        "/api/v1/validations/example-answer/attempts",
                        headers={**headers, "Request-ID": str(uuid4())},
                        json={"answer": " ECHO-7 "},
                    ),
                    client.post(
                        "/api/v1/validations/example-answer/attempts",
                        headers={**headers, "Request-ID": str(uuid4())},
                        json={"answer": " ECHO-7 "},
                    ),
                )
                assert completed.json() == repeated.json() == {"content": {"accepted": True}, "followups": []}

                completed_hints = await client.get("/api/v1/hints", headers=headers)
                assert len(completed_hints.json()["hints"]) == 3
                gated_hint = next(
                    hint for hint in completed_hints.json()["hints"] if hint["vtb_cost"] == 5
                )
                insufficient = await client.post(
                    f"/api/v1/hints/{gated_hint['hint_id']}/disclose",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert insufficient.status_code == 409
                assert insufficient.json()["type"].endswith("/insufficient-credits")
                assert (await client.get("/api/v1/credits", headers=headers)).json()["vtb"] == 3

                admin_file_id = app.state.runtime.catalogs.files.file_id_for_stable_id("example.admin-control")
                assert (await client.get(f"/api/v1/files/{admin_file_id}", headers=headers)).status_code == 403
                guest_dynamic_tree = await client.get("/api/v1/files/d/tree", headers=headers)
                archive = next(
                    directory
                    for directory in guest_dynamic_tree.json()["directories"]
                    if directory["path"] == "/archive"
                )
                assert [item["path"] for item in archive["files"]] == ["/archive/ADMIN_ACCESS.txt"]
                admin_access = archive["files"][0]
                assert admin_access["content_token"].startswith("act3_")

                expected_admin_access = (
                    "ADMINISTRATOR ACCESS\n\n"
                    f"Player: {player_id}\n"
                    "Username: administrator\n"
                    "Password: admin-echo-9\n"
                ).encode()
                artifact_version = app.state.runtime.catalogs.artifacts.template("example.admin-access").version
                artifact_key = f"artifacts/{player_id}/{artifact_version}"
                assert object_store.objects[artifact_key] == expected_admin_access

                administrator_login = await client.post(
                    "/api/v1/vac/login",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"username": "administrator", "password": "admin-echo-9"},
                )
                assert administrator_login.status_code == 200
                assert administrator_login.json()["content"]["current_account"]["account_id"] == "example.admin"

                admin_tree = await client.get("/api/v1/files/tree", headers=headers)
                assert [directory["path"] for directory in admin_tree.json()["directories"]] == ["/public", "/admin"]
                assert (await client.get(f"/api/v1/files/{admin_file_id}", headers=headers)).status_code == 200
                admin_archive = await client.get("/api/v1/files/d/ls", params={"path": "/archive"}, headers=headers)
                assert admin_archive.status_code == 200
                assert admin_archive.json()["files"] == []
                admin_scripts = await client.get("/api/v1/scripts", headers=headers)
                assert [item["stable_id"] for item in admin_scripts.json()["items"]] == ["example.admin"]

                rejected_as_admin = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"answer": "echo-7"},
                )
                assert rejected_as_admin.json() == {"content": {"accepted": False}, "followups": []}

            assert object_store.upload_keys == [
                "static/example/assets/public/README.txt",
                "static/example/assets/public/GUEST_ACCESS.txt",
                "static/example/assets/admin/CONTROL.txt",
                "static/example/assets/hints/echo-clue.txt",
                "static/example/assets/hints/archive-clue.txt",
                "static/example/assets/hints/final-clue.txt",
                artifact_key,
            ]

    asyncio.run(scenario())
