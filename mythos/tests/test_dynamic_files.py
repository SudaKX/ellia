from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from _helpers.object_store import FakeObjectStore
from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.core.file_ids import FileIdCodec
from mythos.auth.tokens import decode_access_token
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerArtifact, PlayerArtifactNode
from mythos.registry.artifacts import (
    ArtifactNodeTemplate,
    ArtifactRegistry,
    ArtifactTemplate,
    module_handler,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import FileReference, NodeDisplayParams, StaticNodeSpec

pytestmark = pytest.mark.anyio


def _display(label: str) -> NodeDisplayParams:
    return NodeDisplayParams(label=label, icon="document")


@module_handler("test")(1)
async def _artifact_generator(_context):
    from mythos.registry.artifacts import RawArtifact

    return RawArtifact(b"generated", meta={"ok": True})


@module_handler("test")(1)
async def _node_generator(_player, _meta, node):
    node.path = "/dynamic/result.txt"
    return node


_FILE_ID_SIGNING_KEY = SecretStr("test-file-id-signing-key-with-at-least-32-bytes")
_FILE_IDS = FileIdCodec(_FILE_ID_SIGNING_KEY.get_secret_value())


def _setup_registries():
    registries = RegistryBundle()
    registries.files.register_source(FileReference("test", "assets/file.txt", "text/plain"))
    registries.files.register_node(
        StaticNodeSpec.file(
            "test.static",
            "/static/file.txt",
            "test:assets/file.txt",
            "file.txt",
            display=_display("Static"),
        )
    )
    artifact_template = ArtifactTemplate(
        artifact_id="test.artifact",
        media_type="text/plain",
        download_name="result.txt",
        generator=_artifact_generator,
    )
    registries.artifacts.register_template(artifact_template)
    node_template = ArtifactNodeTemplate(
        stable_id="test.artifact-node",
        path="/dynamic/result.txt",
        artifact_locator="test.artifact",
        display=_display("Result"),
        node_generator=_node_generator,
    )
    registries.artifacts.register_node(node_template)
    return registries, artifact_template


async def _seed_artifact(
    session: AsyncSession,
    player_id: UUID,
    artifact_version: str,
    node_version: str,
) -> None:
    artifact = PlayerArtifact(
        player_id=player_id,
        artifact_id="test.artifact",
        version=artifact_version,
        object_key=f"artifacts/{player_id}/{artifact_version}",
        content_digest="sha256:" + "a" * 64,
        media_type="text/plain",
        size_bytes=9,
        download_name="result.txt",
        meta={"ok": True},
    )
    node = PlayerArtifactNode(
        player_id=player_id,
        node_id="test.artifact-node",
        artifact_id="test.artifact",
        path="/dynamic/result.txt",
        version=node_version,
        display=_display("Result").as_dict(),
        hidden=False,
        download_name=None,
    )
    session.add_all([artifact, node])
    await session.commit()


async def test_dynamic_endpoints_include_artifact_nodes(tmp_path) -> None:
    puzzle_root = tmp_path / "puzzles"
    source_file = puzzle_root / "test" / "assets" / "file.txt"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("static", encoding="utf-8")
    registries, artifact_template = _setup_registries()
    object_store = FakeObjectStore()
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'dynamic.sqlite3').as_posix()}",
        jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
        refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
        file_id_signing_key=_FILE_ID_SIGNING_KEY,
        refresh_cookie_secure=False,
        puzzle_root=puzzle_root,
    )
    database = Database(settings.database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.dispose()

    app = create_app(settings, registries=registries, object_store=object_store)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            registered = await client.post(
                "/api/v1/auth/register",
                json={"username": "dynamic-player", "password": "correct-horse-battery"},
            )
            assert registered.status_code == 201
            access_token = registered.json()["access_token"]
            player_id = decode_access_token(access_token, settings).player_id
            headers = {"Authorization": f"Bearer {access_token}"}

            async with database.session_factory() as session:
                await _seed_artifact(
                    session,
                    player_id,
                    artifact_template.version,
                    app.state.runtime.catalogs.artifacts.node_version("test.artifact-node"),
                )

            static_listing = await client.get("/api/v1/files/ls", headers=headers)
            assert static_listing.json()["directories"] == [{"path": "/static", "display": {"label": "static", "description": None, "icon": "folder", "sort_order": 0}}]

            dynamic_root = await client.get("/api/v1/files/d/ls", headers=headers)
            assert dynamic_root.status_code == 200
            assert [item["path"] for item in dynamic_root.json()["directories"]] == ["/dynamic", "/static"]
            dynamic_tree_version = dynamic_root.json()["tree_version"]
            assert dynamic_tree_version.startswith("pft3_")

            dynamic_dir = await client.get("/api/v1/files/d/ls", params={"path": "/dynamic"}, headers=headers)
            assert dynamic_dir.status_code == 200
            assert len(dynamic_dir.json()["files"]) == 1
            file_item = dynamic_dir.json()["files"][0]
            assert file_item["path"] == "/dynamic/result.txt"

            tree = await client.get("/api/v1/files/d/tree", params={"path": "/dynamic"}, headers=headers)
            assert tree.status_code == 200
            assert tree.json()["files"][0]["path"] == "/dynamic/result.txt"

            file_id = _FILE_IDS.encode("test.artifact-node")
            metadata = await client.get(f"/api/v1/files/{file_id}", headers=headers)
            assert metadata.status_code == 200
            assert metadata.json()["path"] == "/dynamic/result.txt"
            assert metadata.json()["download_name"] == "result.txt"
            assert metadata.json()["tree_version"] == dynamic_tree_version

            content_token = metadata.json()["content_token"]
            assert content_token.startswith("act3_")
            content_url = await client.get(
                f"/api/v1/files/{file_id}/{content_token}/content-url",
                headers=headers,
            )
            assert content_url.status_code == 200
            assert content_url.json()["url"] == (
                f"https://objects.test/artifacts/{player_id}/"
                f"{artifact_template.version}?expires=43200"
            )

            version = await client.get("/api/v1/files/d/version", headers=headers)
            assert version.status_code == 200
            assert version.json()["tree_version"] == dynamic_tree_version

    await database.dispose()
