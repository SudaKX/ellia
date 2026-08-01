import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import SecretStr

from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base
from _helpers.object_store import FakeObjectStore


def test_example_module_unlocks_archive_and_generates_report_with_fake_object_store(tmp_path: Path) -> None:
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

                initial_progress = await client.get("/api/v1/progress", headers=headers)
                assert initial_progress.json()["unlocked_nodes"] == ["example.entry"]
                assert initial_progress.json()["frontier_nodes"] == ["example.entry"]
                assert initial_progress.json()["checkpoint_sequence"] == -1

                initial_tree = await client.get("/api/v1/files/tree", headers=headers)
                assert [directory["path"] for directory in initial_tree.json()["directories"]] == ["/public"]
                assert (await client.get("/api/v1/files/ls", params={"path": "/archive"}, headers=headers)).status_code == 404
                initial_dynamic_tree = await client.get("/api/v1/files/d/tree", headers=headers)
                assert [directory["path"] for directory in initial_dynamic_tree.json()["directories"]] == ["/public"]
                assert initial_dynamic_tree.json()["tree_version"] == initial_tree.json()["tree_version"]

                initial_scripts = await client.get("/api/v1/scripts", headers=headers)
                assert initial_scripts.json()["items"] == [
                    {
                        "stable_id": "example.boot",
                        "revision": "1",
                        "body": {
                            "schema_version": 1,
                            "kind": "answer-validator",
                            "validation_id": "example-answer",
                            "input": {"name": "answer", "label": "Access token"},
                            "lines": ["Recovery console online.", "Read /public/README.txt."],
                        },
                    }
                ]

                result_file_id = app.state.runtime.catalogs.files.file_id_for_stable_id("example.archive-result")
                assert (await client.get(f"/api/v1/files/{result_file_id}", headers=headers)).status_code == 403

                rejected = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"answer": "wrong"},
                )
                assert rejected.json() == {"content": {"accepted": False}, "followups": []}
                assert (await client.get("/api/v1/progress", headers=headers)).json() == initial_progress.json()

                request_id = str(uuid4())
                completed = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": request_id},
                    json={"answer": " ECHO-7 "},
                )
                replayed = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": request_id},
                    json={"answer": " ECHO-7 "},
                )
                assert completed.json() == replayed.json() == {"content": {"accepted": True}, "followups": []}

                completed_progress = await client.get("/api/v1/progress", headers=headers)
                assert completed_progress.json()["unlocked_nodes"] == ["example.completed", "example.entry"]
                assert completed_progress.json()["frontier_nodes"] == ["example.completed"]
                assert completed_progress.json()["checkpoint_sequence"] == 0
                assert completed_progress.json()["version"] == initial_progress.json()["version"] + 1

                completed_tree = await client.get("/api/v1/files/tree", headers=headers)
                directories = {item["path"]: item for item in completed_tree.json()["directories"]}
                assert [item["path"] for item in directories["/archive"]["files"]] == ["/archive/result.txt"]
                result_file = directories["/archive"]["files"][0]
                content_url = await client.get(
                    f"/api/v1/files/{result_file['file_id']}/{result_file['content_token']}/content-url",
                    headers=headers,
                )
                assert content_url.json()["url"] == (
                    "https://objects.test/static/example/assets/archive/result.txt?expires=43200"
                )

                dynamic_tree = await client.get("/api/v1/files/d/tree", headers=headers)
                dynamic_directories = {item["path"]: item for item in dynamic_tree.json()["directories"]}
                report_file = next(
                    item
                    for item in dynamic_directories["/archive"]["files"]
                    if item["path"] == "/archive/recovery-report.txt"
                )
                assert [item["path"] for item in dynamic_directories["/archive"]["files"]] == [
                    "/archive/result.txt",
                    "/archive/recovery-report.txt",
                ]
                assert report_file["content_token"].startswith("act1_")
                assert dynamic_tree.json()["tree_version"] != completed_tree.json()["tree_version"]

                report_metadata = await client.get(
                    f"/api/v1/files/{report_file['file_id']}",
                    headers=headers,
                )
                assert report_metadata.json()["download_name"] == "recovery-report.txt"
                assert report_metadata.json()["path"] == "/archive/recovery-report.txt"

                expected_report = (
                    "EXAMPLE RECOVERY REPORT\n\n"
                    f"Player: {player_id}\n"
                    "Status: archive recovered\n"
                ).encode()
                artifact_key = (
                    f"artifacts/{player_id}/example.recovery-report/1/"
                    f"{hashlib.sha256(expected_report).hexdigest()}"
                )
                report_content_url = await client.get(
                    f"/api/v1/files/{report_file['file_id']}/{report_file['content_token']}/content-url",
                    headers=headers,
                )
                assert report_content_url.json()["url"] == f"https://objects.test/{artifact_key}?expires=43200"
                assert object_store.objects[artifact_key] == expected_report

                completed_scripts = await client.get("/api/v1/scripts", headers=headers)
                assert [item["stable_id"] for item in completed_scripts.json()["items"]] == [
                    "example.boot",
                    "example.completed",
                ]

                resubmitted = await client.post(
                    "/api/v1/validations/example-answer/attempts",
                    headers={**headers, "Request-ID": str(uuid4())},
                    json={"answer": "echo-7"},
                )
                assert resubmitted.json() == {"content": {"accepted": True}, "followups": []}
                assert (await client.get("/api/v1/progress", headers=headers)).json() == completed_progress.json()

        assert object_store.upload_keys == [
            "static/example/assets/public/README.txt",
            "static/example/assets/archive/result.txt",
            artifact_key,
        ]

        assert object_store.request_keys == [
            "static/example/assets/archive/result.txt",
            artifact_key,
        ]

    asyncio.run(scenario())
