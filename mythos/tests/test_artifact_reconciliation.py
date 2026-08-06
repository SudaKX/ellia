from uuid import UUID

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import delete, update
from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerArtifact, PlayerArtifactNode, PlayerArtifactState
from mythos.registry.artifacts import (
    ArtifactNodeTemplate,
    ArtifactTemplate,
    RawArtifact,
    module_handler,
)
from mythos.registry.bundle import RegistryBundle
from mythos.registry.files import NodeDisplayParams


pytestmark = pytest.mark.anyio


@module_handler("reconciliation")(1)
async def _artifact_v1(_context) -> RawArtifact:
    return RawArtifact(b"v1", meta={"label": "report.txt"})


@module_handler("reconciliation")(2)
async def _artifact_v2(_context) -> RawArtifact:
    return RawArtifact(b"v2", meta={"label": "updated-report.txt"})


@module_handler("reconciliation")(1)
async def _node_generator(_player, meta, node):
    node.display = NodeDisplayParams(label=meta["label"], icon="document")
    return node


@module_handler("reconciliation")(2)
async def _node_generator_v2(_player, _meta, node):
    node.display = NodeDisplayParams(label="updated-report.txt", icon="document")
    return node


def _registries(generator, node_generator=_node_generator) -> RegistryBundle:
    registries = RegistryBundle()
    registries.artifacts.register_template(
        ArtifactTemplate(
            artifact_id="reconciliation.report",
            media_type="text/plain",
            download_name="report.txt",
            generator=generator,
        )
    )
    registries.artifacts.register_node(
        ArtifactNodeTemplate(
            stable_id="reconciliation.report-file",
            path="/reports/report.txt",
            artifact_locator="reconciliation.report",
            display=NodeDisplayParams(label="report.txt", icon="document"),
            node_generator=node_generator,
        )
    )
    return registries


async def _create_artifact(app, player_id: UUID) -> tuple[str, int]:
    async with app.state.database.session_factory() as session:
        async with session.begin():
            player = await app.state.runtime.player_factory.load(session, player_id, writable=True)
            artifact = await player.artifacts.generate_artifact("reconciliation.report", player)
            await player.artifacts.generate_node("reconciliation.report-file", player)
            return artifact.version, player.artifacts.player_version


async def _artifact_state(app, player_id: UUID) -> tuple[str, int]:
    async with app.state.database.session_factory() as session:
        artifact = await session.get(PlayerArtifact, (player_id, "reconciliation.report"))
        state = await session.get(PlayerArtifactState, player_id)
        assert artifact is not None
        assert state is not None
        return artifact.version, state.version


async def _node_version(app, player_id: UUID) -> str:
    async with app.state.database.session_factory() as session:
        node = await session.get(PlayerArtifactNode, (player_id, "reconciliation.report-file"))
        assert node is not None
        return node.version


async def _node_display_label(app, player_id: UUID) -> str:
    async with app.state.database.session_factory() as session:
        node = await session.get(PlayerArtifactNode, (player_id, "reconciliation.report-file"))
        assert node is not None
        return node.display["label"]


async def test_startup_reconciliation_skips_matching_snapshot_and_refreshes_changed_artifact(tmp_path) -> None:
    settings = Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'reconciliation.sqlite3').as_posix()}",
        artifact_template_snapshot_path=tmp_path / "artifact-templates.json",
        jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
        refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
        file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
        refresh_cookie_secure=False,
    )
    store = FakeObjectStore()

    first = create_app(settings, registries=_registries(_artifact_v1), object_store=store)
    async with first.router.lifespan_context(first):
        async with first.state.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        transport = httpx.ASGITransport(app=first)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/register",
                json={"username": "reconciliation-player", "password": "correct-horse-battery"},
            )
        player_id = decode_access_token(response.json()["access_token"], settings).player_id
        first_version, first_player_version = await _create_artifact(first, player_id)
        initial_node_version = await _node_version(first, player_id)
        assert first_player_version == 2

    assert settings.artifact_snapshot_path.exists()
    upload_count = len(store.uploads)

    unchanged = create_app(settings, registries=_registries(_artifact_v1), object_store=store)
    async with unchanged.router.lifespan_context(unchanged):
        version, player_version = await _artifact_state(unchanged, player_id)
        assert version == first_version
        assert player_version == first_player_version
    assert len(store.uploads) == upload_count

    # Migration 0006 maps the legacy revision into this field without creating state.
    async with unchanged.state.database.session_factory() as session:
        async with session.begin():
            await session.execute(
                update(PlayerArtifact)
                .where(PlayerArtifact.player_id == player_id)
                .values(version="legacy-version")
            )
            await session.execute(delete(PlayerArtifactState).where(PlayerArtifactState.player_id == player_id))

    legacy = create_app(settings, registries=_registries(_artifact_v1), object_store=store)
    async with legacy.router.lifespan_context(legacy):
        version, player_version = await _artifact_state(legacy, player_id)
        assert version == first_version
        assert player_version == 1
        async with legacy.state.database.session_factory() as session:
            artifact = await session.get(PlayerArtifact, (player_id, "reconciliation.report"))
            assert artifact is not None
            assert artifact.object_key == f"artifacts/{player_id}/{version}"
    assert len(store.uploads) == upload_count + 1
    upload_count = len(store.uploads)

    changed = create_app(settings, registries=_registries(_artifact_v2), object_store=store)
    async with changed.router.lifespan_context(changed):
        version, player_version = await _artifact_state(changed, player_id)
        first_node_version = await _node_version(changed, player_id)
        assert version != first_version
        assert version == changed.state.runtime.catalogs.artifacts.template("reconciliation.report").version
        assert first_node_version != initial_node_version
        assert await _node_display_label(changed, player_id) == "updated-report.txt"
        assert player_version == 3
    assert len(store.uploads) == upload_count + 1

    node_changed = create_app(
        settings,
        registries=_registries(_artifact_v2, _node_generator_v2),
        object_store=store,
    )
    async with node_changed.router.lifespan_context(node_changed):
        version, player_version = await _artifact_state(node_changed, player_id)
        node_version = await _node_version(node_changed, player_id)
        assert version == changed.state.runtime.catalogs.artifacts.template("reconciliation.report").version
        assert node_version != first_node_version
        assert player_version == 4
    assert len(store.uploads) == upload_count + 1
