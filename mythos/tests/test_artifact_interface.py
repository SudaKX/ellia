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
)
from mythos.registry.files import DisplayParams
from mythos.registry.files.tree import FileTree, TreeNode


def _display(label: str) -> DisplayParams:
    return DisplayParams(label=label, icon="document")


async def _artifact_generator(_context):
    return RawArtifact(b"dynamic content", meta={"answer": 42})


async def _node_generator(_context, node):
    node.path = "/dynamic/result.txt"
    node.display = _display("Result")
    return node


def _make_catalog():
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="test.artifact",
            revision="1",
            media_type="text/plain",
            download_name="result.txt",
            generator=_artifact_generator,
        )
    )
    registry.register_node(
        ArtifactNodeTemplate(
            stable_id="test.artifact-node",
            path="/placeholder.txt",
            revision="1",
            artifact_locator="test.artifact",
            display=_display("Placeholder"),
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

    nodes = await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    assert len(nodes) == 1
    node = nodes[0]
    assert node.path == "/dynamic/result.txt"
    assert node.stable_id == "test.artifact-node"
    assert node.artifact_locator == "test.artifact"

    await session.commit()

    assert len(store.uploads) == 1
    object_key, data, media_type = store.uploads[0]
    assert data == b"dynamic content"
    assert media_type == "text/plain"
    assert object_key.startswith(f"artifacts/{interface.player_id}/test.artifact/1/")

    artifact = await session.get(PlayerArtifact, (interface.player_id, "test.artifact"))
    assert artifact is not None
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
        await interface.generate("test.artifact", None)  # type: ignore[arg-type]


async def test_artifact_interface_regenerating_updates_records(session) -> None:
    store = FakeObjectStore()
    interface = await ArtifactInterface.load(
        session,
        uuid4(),
        _CATALOG,
        store,
        _FILE_IDS,
        writable=True,
    )

    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    first_version = interface.tree_nodes()[0].content.object_ref.version_id
    first_hash = interface.version_hash()

    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    second_version = interface.tree_nodes()[0].content.object_ref.version_id
    second_hash = interface.version_hash()

    assert second_version != first_version
    assert second_hash != first_hash
    assert len(store.uploads) == 2


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

    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    tree_node = interface.tree_nodes()[0]
    assert tree_node.content is not None
    assert tree_node.content.content_token.startswith("act1_")


async def test_artifact_interface_object_key_is_deterministic(session) -> None:
    player_id = uuid4()
    key = ArtifactInterface._artifact_object_key(
        player_id,
        "test.artifact",
        "2",
        "sha256-digest",
    )
    assert key == f"artifacts/{player_id}/test.artifact/2/sha256-digest"


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


async def test_artifact_interface_regenerating_clears_tree_cache(session) -> None:
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

    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    first = interface.get_tree(static_tree, _FILE_IDS)

    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    second = interface.get_tree(static_tree, _FILE_IDS)
    assert first is not second


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

    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    await interface.generate("test.artifact", None)  # type: ignore[arg-type]
    await session.commit()

    count = await session.scalar(sa_select(func.count()).select_from(PlayerArtifact))
    assert count == 1


def _make_hidden_catalog():
    registry = ArtifactRegistry()
    registry.register_template(
        ArtifactTemplate(
            artifact_id="hidden.artifact",
            revision="1",
            media_type="text/plain",
            download_name="hidden.txt",
            generator=_artifact_generator,
        )
    )

    async def _hidden_node_generator(_context, node):
        node.path = "/dynamic/hidden.txt"
        node.hidden = True
        return node

    registry.register_node(
        ArtifactNodeTemplate(
            stable_id="hidden.artifact-node",
            path="/placeholder.txt",
            revision="1",
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

    nodes = await interface.generate("hidden.artifact", None)  # type: ignore[arg-type]
    assert len(nodes) == 1
    assert nodes[0].hidden is True
    assert interface.tree_nodes()[0].definition.hidden is True


