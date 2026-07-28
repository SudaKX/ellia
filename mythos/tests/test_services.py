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
from mythos.registry.files import DisplayParams, FileReference, ObjectReference, VirtualNode
from mythos.registry.scripts import Script
from mythos.services.object_store.service import PresignedObjectUrl


class FakeObjectStore:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str, str]] = []
        self.uploads: list[str] = []

    async def presign_get(
        self,
        reference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
        response_cache_control: str,
        response_expires_at,
    ) -> PresignedObjectUrl:
        self.requests.append(
            (reference.key, content_disposition, response_cache_control, response_expires_at)
        )
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
        hidden_leaf_rule_calls = 0

        def child_rule(_player) -> bool:
            nonlocal child_rule_calls
            child_rule_calls += 1
            return True

        def hidden_leaf_rule(_player) -> bool:
            nonlocal hidden_leaf_rule_calls
            hidden_leaf_rule_calls += 1
            return False

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
                VirtualNode.file(
                    stable_id,
                    path,
                    "1",
                    source_locator,
                    download_name,
                    access_rule,
                    display=DisplayParams(label=download_name, icon="document"),
                )
            )

        register_file("test.readme", "/README.txt", "assets/readme.txt", "README.txt", "hello")
        register_file("test.guide", "/docs/guide.txt", "assets/guide.txt", "guide.txt", "guide")
        registries.files.register_node(
            VirtualNode.directory(
                "test.private-directory",
                "/private",
                "1",
                lambda _player: False,
                display=DisplayParams(label="Private", icon="folder"),
            )
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
            VirtualNode.directory(
                "test.open-directory",
                "/open",
                "1",
                lambda _player: True,
                display=DisplayParams(label="Open", icon="folder"),
            )
        )
        register_file("test.open-file", "/open/public.txt", "assets/open-public.txt", "public.txt", "public")
        registries.files.register_node(
            VirtualNode.directory(
                "test.hidden-directory",
                "/open/hidden",
                "1",
                lambda _player: False,
                display=DisplayParams(label="Hidden", icon="folder"),
            )
        )
        register_file(
            "test.hidden-file",
            "/open/hidden/secret.txt",
            "assets/open-hidden.txt",
            "secret.txt",
            "hidden",
        )
        registries.files.register_node(
            VirtualNode.directory(
                "test.empty-directory",
                "/empty",
                "1",
                display=DisplayParams(label="Empty", icon="folder"),
            )
        )
        registries.files.register_node(
            VirtualNode.directory(
                "test.visible-empty-directory",
                "/visible-empty",
                "1",
                display=DisplayParams(label="Visible empty", icon="folder"),
            )
        )
        register_file(
            "test.visible-empty-file",
            "/visible-empty/hidden.txt",
            "assets/visible-empty.txt",
            "hidden.txt",
            "hidden",
            hidden_leaf_rule,
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
            file_content_url_ttl_seconds=60,
            file_content_cache_max_age_seconds=55,
            file_download_url_ttl_seconds=60,
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
                listing = await client.get("/api/v1/files/ls", headers=headers)
                assert listing.headers["cache-control"] == "no-store"
                assert listing.headers["vary"] == "Authorization"
                assert listing.json()["path"] == "/"
                assert [item["path"] for item in listing.json()["directories"]] == [
                    "/docs",
                    "/empty",
                    "/open",
                    "/visible-empty",
                ]
                assert listing.json()["directories"][1]["display"] == {
                    "label": "Empty",
                    "description": None,
                    "icon": "folder",
                    "sort_order": 0,
                }
                assert len(listing.json()["files"]) == 1
                readme_id = listing.json()["files"][0]["file_id"]
                readme_token = listing.json()["files"][0]["content_token"]
                assert listing.json()["tree_version"].startswith("ft1_")
                assert readme_token.startswith("ct1_")
                assert "stable_id" not in listing.json()["files"][0]
                assert listing.json()["files"][0]["display"]["label"] == "README.txt"
                assert hidden_leaf_rule_calls == 0

                tree = await client.get("/api/v1/files/tree", headers=headers)
                assert tree.headers["cache-control"] == "no-store"
                assert tree.json()["tree_version"] == listing.json()["tree_version"]
                assert tree.json()["display"]["label"] == "/"
                assert [item["path"] for item in tree.json()["directories"]] == [
                    "/docs",
                    "/empty",
                    "/open",
                    "/visible-empty",
                ]
                docs_tree = next(item for item in tree.json()["directories"] if item["path"] == "/docs")
                assert docs_tree["files"][0]["path"] == "/docs/guide.txt"
                visible_empty_tree = next(
                    item for item in tree.json()["directories"] if item["path"] == "/visible-empty"
                )
                assert visible_empty_tree["directories"] == []
                assert visible_empty_tree["files"] == []
                assert hidden_leaf_rule_calls == 1

                empty_directory = await client.get(
                    "/api/v1/files/ls",
                    params={"path": "/empty"},
                    headers=headers,
                )
                assert empty_directory.status_code == 200
                assert empty_directory.json()["directories"] == []
                assert empty_directory.json()["files"] == []

                open_directory = await client.get(
                    "/api/v1/files/ls",
                    params={"path": "/open"},
                    headers=headers,
                )
                open_listing = open_directory.json()
                assert open_listing["path"] == "/open"
                assert open_listing["directories"] == []
                assert open_listing["tree_version"] == listing.json()["tree_version"]
                assert open_listing["files"] == [
                    {
                        "file_id": app.state.runtime.catalogs.files.file_id_for_stable_id("test.open-file"),
                        "path": "/open/public.txt",
                        "revision": "1",
                        "media_type": "text/plain",
                        "size_bytes": 6,
                        "content_token": open_listing["files"][0]["content_token"],
                        "display": {
                            "label": "public.txt",
                            "description": None,
                            "icon": "document",
                            "sort_order": 0,
                        },
                    }
                ]
                assert open_listing["files"][0]["content_token"].startswith("ct1_")

                metadata = await client.get(f"/api/v1/files/{readme_id}", headers=headers)
                assert metadata.status_code == 200
                assert metadata.headers["cache-control"] == "no-store"
                assert metadata.headers["vary"] == "Authorization"
                assert metadata.json()["download_name"] == "README.txt"
                assert metadata.json()["content_token"] == readme_token
                assert metadata.json()["tree_version"] == listing.json()["tree_version"]
                assert metadata.json()["display"]["label"] == "README.txt"
                version = await client.get("/api/v1/files/version", headers=headers)
                assert version.json() == {"tree_version": listing.json()["tree_version"]}
                assert version.headers["cache-control"] == "private, no-cache"
                assert version.headers["vary"] == "Authorization"
                unchanged_version = await client.get(
                    "/api/v1/files/version",
                    headers={**headers, "If-None-Match": version.headers["etag"]},
                )
                assert unchanged_version.status_code == 304

                content_url = await client.get(
                    f"/api/v1/files/{readme_id}/{readme_token}/content-url",
                    headers=headers,
                )
                assert content_url.status_code == 200
                assert content_url.headers["cache-control"] == "private, max-age=55, must-revalidate"
                assert content_url.headers["vary"] == "Authorization"
                assert content_url.json()["content_token"] == readme_token
                assert content_url.json()["url"] == "https://objects.test/static/test/assets/readme.txt?expires=60"
                stale_content_url = await client.get(
                    f"/api/v1/files/{readme_id}/ct1_stale/content-url",
                    headers=headers,
                )
                assert stale_content_url.status_code == 412

                download_url = await client.get(
                    f"/api/v1/files/{readme_id}/{readme_token}/download-url",
                    headers=headers,
                )
                assert download_url.status_code == 200
                assert download_url.headers["cache-control"] == "no-store"
                assert download_url.json()["url"] == "https://objects.test/static/test/assets/readme.txt?expires=60"

                private_id = app.state.runtime.catalogs.files.file_id_for_stable_id("test.private")
                private_file = app.state.runtime.catalogs.files.file(private_id)
                assert private_file.content is not None
                private_directory = await client.get(
                    "/api/v1/files/ls",
                    params={"path": "/private"},
                    headers=headers,
                )
                assert private_directory.status_code == 404
                private_url = await client.get(
                    f"/api/v1/files/{private_id}/{private_file.content.content_token}/download-url",
                    headers=headers,
                )
                assert private_url.status_code == 403
                assert child_rule_calls == 0
                assert object_store.uploads == [
                    "static/test/assets/readme.txt",
                    "static/test/assets/guide.txt",
                    "static/test/assets/private.txt",
                    "static/test/assets/open-public.txt",
                    "static/test/assets/open-hidden.txt",
                    "static/test/assets/visible-empty.txt",
                ]
                assert object_store.requests[0][:3] == (
                    "static/test/assets/readme.txt",
                    'inline; filename="README.txt"',
                    "private, must-revalidate",
                )
                assert object_store.requests[0][3] is not None
                assert object_store.requests[1] == (
                    "static/test/assets/readme.txt",
                    'attachment; filename="README.txt"',
                    "no-store",
                    None,
                )

                scripts = await client.get("/api/v1/scripts", headers=headers)
                assert scripts.json() == {
                    "items": [{"stable_id": "test.intro", "revision": "1", "body": {"lines": ["hello"]}}]
                }

    asyncio.run(scenario())
