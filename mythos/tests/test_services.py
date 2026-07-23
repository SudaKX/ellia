import asyncio
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileContent, ObjectReference, VirtualNode
from mythos.registry.scripts import Script
from mythos.services.object_store.service import PresignedObjectUrl


class FakeObjectStore:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    async def presign_get(self, reference, *, expires_in_seconds: int, content_disposition: str) -> PresignedObjectUrl:
        self.requests.append((reference.key, content_disposition))
        return PresignedObjectUrl(
            url=f"https://objects.test/{reference.key}?expires={expires_in_seconds}",
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )


def _object(key: str, size: int) -> ObjectReference:
    return ObjectReference(key, "sha256:" + "a" * 64, "text/plain", size, "test-version")


def test_global_services_read_frozen_registered_content(tmp_path) -> None:
    async def scenario() -> None:
        child_rule_calls = 0

        def child_rule(_player) -> bool:
            nonlocal child_rule_calls
            child_rule_calls += 1
            return True

        registries = RegistryBundle()
        registries.files.register(
            VirtualNode(
                "test.readme",
                "/README.txt",
                "1",
                FileContent(_object("test/readme.txt", 5), "README.txt"),
            )
        )
        registries.files.register(
            VirtualNode(
                "test.guide",
                "/docs/guide.txt",
                "1",
                FileContent(_object("test/guide.txt", 5), "guide.txt"),
            )
        )
        registries.files.register(
            VirtualNode(
                "test.private-directory",
                "/private",
                "1",
                access_rule=lambda _player: False,
            )
        )
        registries.files.register(
            VirtualNode(
                "test.private",
                "/private/secret.txt",
                "1",
                FileContent(_object("test/private.txt", 7), "private.txt"),
                access_rule=child_rule,
            )
        )
        registries.files.register(
            VirtualNode(
                "test.open-directory",
                "/open",
                "1",
                access_rule=lambda _player: True,
            )
        )
        registries.files.register(
            VirtualNode(
                "test.open-file",
                "/open/public.txt",
                "1",
                FileContent(_object("test/open-public.txt", 6), "public.txt"),
            )
        )
        registries.files.register(
            VirtualNode(
                "test.hidden-directory",
                "/open/hidden",
                "1",
                access_rule=lambda _player: False,
            )
        )
        registries.files.register(
            VirtualNode(
                "test.hidden-file",
                "/open/hidden/secret.txt",
                "1",
                FileContent(_object("test/open-hidden.txt", 6), "secret.txt"),
            )
        )
        registries.scripts.register(Script("test.intro", "1", {"lines": ["hello"]}))
        object_store = FakeObjectStore()
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'services.sqlite3').as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=registries, object_store=object_store)

        async with app.router.lifespan_context(app):
            first_services = app.state.runtime.services
            assert first_services is app.state.runtime.services
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registered = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "service-player", "password": "correct-horse-battery"},
                )
                headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
                listing = await client.get("/api/v1/files", headers=headers)
                assert listing.json()["path"] == "/"
                assert listing.json()["directories"] == ["/docs", "/open"]
                assert len(listing.json()["files"]) == 1
                readme_id = listing.json()["files"][0]["file_id"]
                assert "stable_id" not in listing.json()["files"][0]

                open_directory = await client.get("/api/v1/files", params={"path": "/open"}, headers=headers)
                assert open_directory.json() == {
                    "path": "/open",
                    "directories": [],
                    "files": [
                        {
                            "file_id": app.state.runtime.catalogs.files.file_id_for_stable_id("test.open-file"),
                            "path": "/open/public.txt",
                            "revision": "1",
                            "media_type": "text/plain",
                            "size_bytes": 6,
                        }
                    ],
                }

                metadata = await client.get(f"/api/v1/files/{readme_id}", headers=headers)
                assert metadata.status_code == 200
                assert metadata.json()["download_name"] == "README.txt"
                content_url = await client.post(f"/api/v1/files/{readme_id}/content-url", headers=headers)
                assert content_url.status_code == 200
                assert content_url.headers["cache-control"] == "no-store"
                assert content_url.json()["url"] == "https://objects.test/test/readme.txt?expires=60"

                private_id = app.state.runtime.catalogs.files.file_id_for_stable_id("test.private")
                private_directory = await client.get("/api/v1/files", params={"path": "/private"}, headers=headers)
                assert private_directory.status_code == 404
                private_url = await client.post(f"/api/v1/files/{private_id}/download-url", headers=headers)
                assert private_url.status_code == 403
                assert child_rule_calls == 0
                assert object_store.requests == [("test/readme.txt", 'inline; filename="README.txt"')]

                scripts = await client.get("/api/v1/scripts", headers=headers)
                assert scripts.json() == {
                    "items": [{"stable_id": "test.intro", "revision": "1", "body": {"lines": ["hello"]}}]
                }

    asyncio.run(scenario())
