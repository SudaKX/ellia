import asyncio
import hashlib
from datetime import UTC, datetime, timedelta

import httpx
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileReference, ObjectReference, VirtualNode
from mythos.registry.scripts import Script
from mythos.services.object_store.service import PresignedObjectUrl


class FakeObjectStore:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.uploads: list[str] = []

    async def presign_get(self, reference, *, expires_in_seconds: int, content_disposition: str) -> PresignedObjectUrl:
        self.requests.append((reference.key, content_disposition))
        return PresignedObjectUrl(
            url=f"https://objects.test/{reference.key}?expires={expires_in_seconds}",
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )


    async def put_file(self, source_path, *, object_key: str, media_type: str) -> ObjectReference:
        content = source_path.read_bytes()
        self.uploads.append(object_key)
        return ObjectReference(
            object_key,
            f"sha256:{hashlib.sha256(content).hexdigest()}",
            media_type,
            len(content),
            f"test-version-{len(self.uploads)}",
        )


def test_global_services_read_frozen_registered_content(tmp_path) -> None:
    async def scenario() -> None:
        child_rule_calls = 0

        def child_rule(_player) -> bool:
            nonlocal child_rule_calls
            child_rule_calls += 1
            return True

        registries = RegistryBundle()
        puzzle_root = tmp_path / "puzzles"

        def register_file(stable_id, path, source_path, download_name, content, access_rule=None) -> None:
            source_file = puzzle_root / "test" / source_path
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text(content, encoding="utf-8")
            source_locator = registries.files.register_source(
                FileReference("test", source_path, "text/plain")
            )
            registries.files.register_node(
                VirtualNode.file(stable_id, path, "1", source_locator, download_name, access_rule)
            )

        register_file("test.readme", "/README.txt", "assets/readme.txt", "README.txt", "hello")
        register_file("test.guide", "/docs/guide.txt", "assets/guide.txt", "guide.txt", "guide")
        registries.files.register_node(
            VirtualNode.directory("test.private-directory", "/private", "1", lambda _player: False)
        )
        register_file(
            "test.private",
            "/private/secret.txt",
            "assets/private.txt",
            "private.txt",
            "private",
            child_rule,
        )
        registries.files.register_node(
            VirtualNode.directory("test.open-directory", "/open", "1", lambda _player: True)
        )
        register_file("test.open-file", "/open/public.txt", "assets/open-public.txt", "public.txt", "public")
        registries.files.register_node(
            VirtualNode.directory("test.hidden-directory", "/open/hidden", "1", lambda _player: False)
        )
        register_file(
            "test.hidden-file",
            "/open/hidden/secret.txt",
            "assets/open-hidden.txt",
            "secret.txt",
            "hidden",
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
            puzzle_root=puzzle_root,
        )
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.dispose()
        app = create_app(settings, registries=registries, object_store=object_store)

        async with app.router.lifespan_context(app):
            first_services = app.state.runtime.services
            assert first_services is app.state.runtime.services
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
                assert content_url.json()["url"] == "https://objects.test/static/test/assets/readme.txt?expires=60"

                private_id = app.state.runtime.catalogs.files.file_id_for_stable_id("test.private")
                private_directory = await client.get("/api/v1/files", params={"path": "/private"}, headers=headers)
                assert private_directory.status_code == 404
                private_url = await client.post(f"/api/v1/files/{private_id}/download-url", headers=headers)
                assert private_url.status_code == 403
                assert child_rule_calls == 0
                assert object_store.uploads == [
                    "static/test/assets/readme.txt",
                    "static/test/assets/guide.txt",
                    "static/test/assets/private.txt",
                    "static/test/assets/open-public.txt",
                    "static/test/assets/open-hidden.txt",
                ]
                assert object_store.requests == [("static/test/assets/readme.txt", 'inline; filename="README.txt"')]

                scripts = await client.get("/api/v1/scripts", headers=headers)
                assert scripts.json() == {
                    "items": [{"stable_id": "test.intro", "revision": "1", "body": {"lines": ["hello"]}}]
                }

    asyncio.run(scenario())
