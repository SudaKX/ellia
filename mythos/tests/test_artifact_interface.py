from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.anyio

from _helpers.object_store import FakeObjectStore
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerArtifact
from mythos.players.interfaces.artifacts import ArtifactInterface, ReadOnlyArtifactError
from mythos.registry.artifacts import (
    ArtifactNodeTemplate,
    ArtifactRegistry,
    ArtifactTemplate,
    RawArtifact,
    module_handler,
)
from mythos.registry.files import DisplayParams
from mythos.registry.files.tree import FileTree, TreeNode


def _display(label: str) -> DisplayParams:
    return DisplayParams(label=label, icon="document")


@module_handler("test")(1)
async def _artifact_generator(_context):
    return RawArtifact(b"dynamic content", meta={"answer": 42})


@module_handler("test")(2)
async def _artifact_generator_v2(_context):
    return RawArtifact(b"updated dynamic content", meta={"answer": 43})


@module_handler("test")(1)
async def _node_generator(_context, node):
    node.path = "/dynamic/result.txt"
    node.display = _display("Result")
    return node


def _make_catalog(generator=_artifact_generator):
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="test.artifact",
            media_type="text/plain",
            download_name="result.txt",
            generator=generator,
        )
    )
    registry.register_node(
        ArtifactNodeTemplate(
            stable_id="test.artifact-node",
            path="/placeholder.txt",
            artifact_locator="test.artifact",
            display=_display("Placeholder"),
            node_generator=_node_generator,
        )
    )
    return registry.freeze()


def _make_reassigned_catalog(artifact_locator: str):
    registry = ArtifactRegistry()
    for artifact_id in ("test.artifact-a", "test.artifact-b"):
        registry.register_template(
            ArtifactTemplate(
                artifact_id=artifact_id,
                media_type="text/plain",
                download_name="result.txt",
                generator=_artifact_generator,
            )
        )
    registry.register_node(
        ArtifactNodeTemplate(
            stable_id="test.reassigned-node",
            path="/dynamic/result.txt",
            artifact_locator=artifact_locator,
            display=_display("Result"),
            node_generator=_node_generator,
        )
    )
    return registry.freeze()


_CATALOG = _make_catalog()
_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_artifact_interface_loads_empty_when_no_records(session) -> None:
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        FakeObjectStore(),
        _FILE_IDS,
        writable=False,
    )
    assert interface.tree_nodes() == ()


async def test_artifact_interface_generates_and_persists_artifact(session) -> None:
    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )

    artifact = await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    node = await interface.generate_node("test.artifact-node", None)  # type: ignore[arg-type]
    assert node.path == "/dynamic/result.txt"
    assert node.stable_id == "test.artifact-node"
    assert node.artifact_locator == "test.artifact"

    await session.commit()

    assert len(store.uploads) == 1
    object_key, data, media_type = store.uploads[0]
    assert data == b"dynamic content"
    assert media_type == "text/plain"
    assert artifact.version.startswith("av1_")
    assert object_key.startswith(f"artifacts/{interface.player_id}/test.artifact/{artifact.version}/")

    artifact = await session.get(PlayerArtifact, (interface.player_id, "test.artifact"))
    assert artifact is not None
    assert artifact.version.startswith("av1_")
    assert artifact.download_name == "result.txt"
    assert artifact.meta == {"answer": 42}

    tree_nodes = interface.tree_nodes()
    assert len(tree_nodes) == 1
    assert isinstance(tree_nodes[0], TreeNode)
    assert tree_nodes[0].path == "/dynamic/result.txt"
    assert tree_nodes[0].content is not None
    assert tree_nodes[0].content.download_name == "result.txt"
    assert tree_nodes[0].file_id == _FILE_IDS.encode("test.artifact-node")


async def test_artifact_interface_rejects_generation_when_read_only(session) -> None:
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        FakeObjectStore(),
        _FILE_IDS,
        writable=False,
    )
    with pytest.raises(ReadOnlyArtifactError):
        await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]


async def test_artifact_interface_repeated_generation_is_idempotent(session) -> None:
    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )

    artifact = await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    node = await interface.generate_node("test.artifact-node", None)  # type: ignore[arg-type]
    first_player_version = interface.player_version

    assert await interface.generate_artifact("test.artifact", None) is artifact  # type: ignore[arg-type]
    repeated_node = await interface.generate_node("test.artifact-node", None)  # type: ignore[arg-type]

    assert repeated_node.version == node.version
    assert interface.player_version == first_player_version
    assert len(store.uploads) == 1


async def test_artifact_refresh_reloads_upserted_records_in_same_session(session) -> None:
    store = FakeObjectStore()
    player_id = uuid4()
    initial = await ArtifactInterface.load(
        session,
        player_id,
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )
    await initial.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    await initial.generate_node("test.artifact-node", None)  # type: ignore[arg-type]

    refreshed = await ArtifactInterface.load(
        session,
        player_id,
        _make_catalog(_artifact_generator_v2),
        store,
        _FILE_IDS,
        writable=True,
    )
    artifact = await refreshed.refresh_artifact("test.artifact", None)  # type: ignore[arg-type]
    assert artifact is not None
    first_player_version = refreshed.player_version
    assert artifact.version == _make_catalog(_artifact_generator_v2).template("test.artifact").version

    repeated = await refreshed.refresh_artifact("test.artifact", None)  # type: ignore[arg-type]
    assert repeated is artifact
    assert refreshed.player_version == first_player_version
    assert len(store.uploads) == 2


async def test_refresh_stale_removes_node_reassigned_to_unowned_artifact(session) -> None:
    store = FakeObjectStore()
    player_id = uuid4()
    initial = await ArtifactInterface.load(
        session,
        player_id,
        _make_reassigned_catalog("test.artifact-a"),
        store,
        _FILE_IDS,
        writable=True,
    )
    await initial.generate_artifact("test.artifact-a", None)  # type: ignore[arg-type]
    await initial.generate_node("test.reassigned-node", None)  # type: ignore[arg-type]

    reassigned = await ArtifactInterface.load(
        session,
        player_id,
        _make_reassigned_catalog("test.artifact-b"),
        store,
        _FILE_IDS,
        writable=True,
    )
    await reassigned.refresh_stale(None)  # type: ignore[arg-type]

    assert reassigned.has_node("test.reassigned-node") is False
    assert reassigned.tree_nodes() == ()


async def test_artifact_interface_artifact_content_token_includes_player_id(session) -> None:
    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )

    await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    await interface.generate_node("test.artifact-node", None)  # type: ignore[arg-type]
    tree_node = interface.tree_nodes()[0]
    assert tree_node.content is not None
    assert tree_node.content.content_token.startswith("act2_")


async def test_artifact_interface_object_key_is_deterministic(session) -> None:
    player_id = uuid4()
    key = ArtifactInterface._artifact_object_key(
        player_id,
        "test.artifact",
        _CATALOG.template("test.artifact").version,
        "sha256-digest",
    )
    assert key == (
        f"artifacts/{player_id}/test.artifact/"
        f"{_CATALOG.template('test.artifact').version}/sha256-digest"
    )


async def test_artifact_interface_caches_player_tree(session) -> None:
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        FakeObjectStore(),
        _FILE_IDS,
        writable=True,
    )
    static_tree = FileTree.build({}, {}, _FILE_IDS)

    first = interface.get_tree(static_tree, _FILE_IDS)
    second = interface.get_tree(static_tree, _FILE_IDS)
    assert first is second


async def test_artifact_interface_current_records_preserve_tree_cache(session) -> None:
    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )
    static_tree = FileTree.build({}, {}, _FILE_IDS)

    await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    await interface.generate_node("test.artifact-node", None)  # type: ignore[arg-type]
    first = interface.get_tree(static_tree, _FILE_IDS)

    await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    await interface.generate_node("test.artifact-node", None)  # type: ignore[arg-type]
    assert await interface.refresh_artifact("test.artifact", None) is not None  # type: ignore[arg-type]
    assert await interface.refresh_node("test.artifact-node", None) is not None  # type: ignore[arg-type]
    second = interface.get_tree(static_tree, _FILE_IDS)
    assert first is second
    assert len(store.uploads) == 1


async def test_artifact_interface_upsert_keeps_single_row(session) -> None:
    from sqlalchemy import func, select as sa_select

    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )

    await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    await interface.generate_artifact("test.artifact", None)  # type: ignore[arg-type]
    await session.commit()

    count = await session.scalar(sa_select(func.count()).select_from(PlayerArtifact))
    assert count == 1


def _make_hidden_catalog():
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="hidden.artifact",
            media_type="text/plain",
            download_name="hidden.txt",
            generator=_artifact_generator,
        )
    )

    @module_handler("hidden")(1)
    async def _hidden_node_generator(_context, node):
        node.path = "/dynamic/hidden.txt"
        node.hidden = True
        return node

    registry.register_node(
        ArtifactNodeTemplate(
            stable_id="hidden.artifact-node",
            path="/placeholder.txt",
            artifact_locator="hidden.artifact",
            display=_display("Hidden"),
            node_generator=_hidden_node_generator,
        )
    )
    return registry.freeze()


async def test_artifact_interface_hidden_node_preserved(session) -> None:
    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _make_hidden_catalog(),
        store,
        _FILE_IDS,
        writable=True,
    )

    await interface.generate_artifact("hidden.artifact", None)  # type: ignore[arg-type]
    node = await interface.generate_node("hidden.artifact-node", None)  # type: ignore[arg-type]
    assert node.hidden is True
    assert interface.tree_nodes()[0].definition.hidden is True


