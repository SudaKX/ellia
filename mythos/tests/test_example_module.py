import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerCreditBalance
from mythos.players.interfaces import PlayerInterfaces
from puzzles.example import ADMIN_ACCOUNT_ID, ADMIN_PASSWORD, ADMIN_USERNAME


def _balance(body: dict, credit_id: str) -> int:
    return next(entry["balance"] for entry in body["credits"] if entry["credit_id"] == credit_id)


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
                assert _balance(initial_credits.json(), "vtb") == 5
                assert _balance(initial_credits.json(), "example.moonstones") == 5
                assert initial_credits.json()["version"] == 2
                assert initial_credits.headers["cache-control"] == "no-store"
                assert "Authorization" in initial_credits.headers["vary"]

                administrator_registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "administrator-only-player", "password": "correct-horse-battery"},
                )
                assert administrator_registration.status_code == 201
                administrator_token = administrator_registration.json()["access_token"]
                administrator_headers = {"Authorization": f"Bearer {administrator_token}"}
                administrator_player_id = decode_access_token(administrator_token, settings).player_id
                async with app.state.database.session_factory() as session:
                    async with session.begin():
                        administrator_player = await app.state.runtime.player_loader.load_writable(
                            session,
                            administrator_player_id,
                            interfaces=PlayerInterfaces.ACCOUNTS,
                        )
                        await administrator_player.accounts.issue(
                            ADMIN_ACCOUNT_ID,
                            ADMIN_USERNAME,
                            ADMIN_PASSWORD,
                        )
                administrator_first_login = await client.post(
                    "/api/v1/vac/login",
                    headers={**administrator_headers, "Request-ID": str(uuid4())},
                    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
                )
                assert administrator_first_login.status_code == 200
                assert administrator_first_login.json()["content"]["current_account"]["account_id"] == ADMIN_ACCOUNT_ID
                administrator_achievements = await client.get("/api/v1/achievement", headers=administrator_headers)
                guest_login_achievement = next(
                    item
                    for item in administrator_achievements.json()["items"]
                    if item["meta"].get("title") == "Guest 已登录"
                )
                assert guest_login_achievement["status"] == "locked"
                assert _balance((await client.get("/api/v1/credits", headers=administrator_headers)).json(), "vtb") == 10

                initial_hints = await client.get("/api/v1/hints", headers=headers)
                assert initial_hints.status_code == 200
                public_hints = initial_hints.json()["hints"]
                assert len(public_hints) == 2
                assert sorted(hint["credit_amount"] for hint in public_hints) == [2, 3]
                assert all(hint["credit_id"] == "vtb" for hint in public_hints)
                assert all(not hint["disclosed"] and "content_token" not in hint for hint in public_hints)
                purchased_hint = next(hint for hint in public_hints if hint["credit_amount"] == 2)
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
                assert _balance((await client.get("/api/v1/credits", headers=headers)).json(), "vtb") == 8

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
                initial_dynamic_version = await client.get("/api/v1/files/d/version", headers=headers)
                assert initial_dynamic_version.status_code == 200
                assert initial_dynamic_version.json()["tree_version"].startswith("pft4_")
                initial_tree = await client.get("/api/v1/files/tree", headers=headers)
                assert [directory["path"] for directory in initial_tree.json()["directories"]] == ["/public"]
                assert (await client.get("/api/v1/files/ls", params={"path": "/admin"}, headers=headers)).status_code == 404
                assert (await client.get("/api/v1/scripts", headers=headers)).json() == {"items": []}

                async with app.state.database.session_factory() as session:
                    vtb_row = await session.scalar(
                        select(PlayerCreditBalance).where(
                            PlayerCreditBalance.player_id == player_id,
                            PlayerCreditBalance.credit_id == "vtb",
                        )
                    )
                    assert vtb_row is not None
                    vtb_row.balance = 15
                    await session.commit()
                at_threshold = await client.post(
                    "/api/v1/achievement/check",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert at_threshold.status_code == 200
                assert at_threshold.json()["content"]["check"]["earned"] == []
                async with app.state.database.session_factory() as session:
                    vtb_row = await session.scalar(
                        select(PlayerCreditBalance).where(
                            PlayerCreditBalance.player_id == player_id,
                            PlayerCreditBalance.credit_id == "vtb",
                        )
                    )
                    assert vtb_row is not None
                    vtb_row.balance = 8
                    await session.commit()

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
                assert guest_login.json()["followups"] == [
                    {
                        "action": "achievement-earned",
                        "data": {
                            "achievement_id": "example.guest-login",
                            "immediate": True,
                            "vtb_reward": 10,
                        },
                    }
                ]
                assert _balance((await client.get("/api/v1/credits", headers=headers)).json(), "vtb") == 18
                guest_achievements = await client.get("/api/v1/achievement", headers=headers)
                assert guest_achievements.status_code == 200
                achievements_by_title = {
                    item["meta"]["title"]: item for item in guest_achievements.json()["items"]
                }
                guest_achievement = achievements_by_title["Guest 已登录"]
                threshold_achievement = achievements_by_title["VTB 储备"]
                assert guest_achievement["immediate"] is True
                assert guest_achievement["status"] == "claimed"
                assert guest_achievement["earned_at"]
                assert guest_achievement["claimed_at"]
                assert threshold_achievement["immediate"] is False
                assert threshold_achievement["status"] == "locked"

                threshold_check = await client.post(
                    "/api/v1/achievement/check",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert threshold_check.status_code == 200
                assert threshold_check.json()["content"]["check"]["earned"] == [threshold_achievement["public_id"]]
                threshold_available = (await client.get("/api/v1/achievement", headers=headers)).json()["items"]
                threshold_achievement = next(
                    item for item in threshold_available if item["public_id"] == threshold_achievement["public_id"]
                )
                assert threshold_achievement["status"] == "available"
                threshold_claim = await client.post(
                    f"/api/v1/achievement/claim/{threshold_achievement['public_id']}",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert threshold_claim.status_code == 200
                assert threshold_claim.json()["content"]["achievement"]["status"] == "claimed"
                assert _balance((await client.get("/api/v1/credits", headers=headers)).json(), "vtb") == 28

                repeated_guest_login = await client.post(
                    "/api/v1/vac/login",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"username": "guest", "password": "guest-echo-7"},
                )
                assert repeated_guest_login.status_code == 200
                assert repeated_guest_login.json()["followups"] == []
                assert _balance((await client.get("/api/v1/credits", headers=headers)).json(), "vtb") == 28

                guest_dynamic_version = await client.get("/api/v1/files/d/version", headers=headers)
                assert guest_dynamic_version.status_code == 200
                assert guest_dynamic_version.json()["tree_version"] != initial_dynamic_version.json()["tree_version"]
                stale_dynamic_version = await client.get(
                    "/api/v1/files/d/version",
                    headers={**headers, "If-None-Match": initial_dynamic_version.headers["etag"]},
                )
                assert stale_dynamic_version.status_code == 200

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

                completed_dynamic_version = await client.get("/api/v1/files/d/version", headers=headers)
                assert completed_dynamic_version.status_code == 200
                assert completed_dynamic_version.json()["tree_version"] != guest_dynamic_version.json()["tree_version"]

                completed_hints = await client.get("/api/v1/hints", headers=headers)
                assert len(completed_hints.json()["hints"]) == 4
                gated_hint = next(
                    hint
                    for hint in completed_hints.json()["hints"]
                    if hint["credit_id"] == "vtb" and hint["credit_amount"] == 5
                )
                gated_purchase = await client.post(
                    f"/api/v1/hints/{gated_hint['hint_id']}/disclose",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert gated_purchase.status_code == 200
                assert gated_purchase.json()["content"]["hint"]["disclosed"] is True
                assert _balance((await client.get("/api/v1/credits", headers=headers)).json(), "vtb") == 23

                moonstone_hint = next(
                    hint
                    for hint in completed_hints.json()["hints"]
                    if hint["credit_id"] == "example.moonstones"
                )
                moonstone_purchase = await client.post(
                    f"/api/v1/hints/{moonstone_hint['hint_id']}/disclose",
                    headers={**headers, "Request-ID": str(uuid4())},
                )
                assert moonstone_purchase.status_code == 200
                moonstone_body = (await client.get("/api/v1/credits", headers=headers)).json()
                assert _balance(moonstone_body, "example.moonstones") == 2
                assert _balance(moonstone_body, "vtb") == 23

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
                assert _balance((await client.get("/api/v1/credits", headers=headers)).json(), "vtb") == 23

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
                "static/example/assets/hints/moonstone-clue.txt",
                artifact_key,
            ]

    asyncio.run(scenario())
