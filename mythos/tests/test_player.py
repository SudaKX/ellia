import mythos.core.commands  # noqa: F401  # ensure commands are loaded before factory to avoid circular import
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.anyio

from _helpers.object_store import FakeObjectStore
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerProgress
from mythos.players.factory import PlayerFactory, PlayerNotFoundError
from mythos.players.interface_selection import PlayerInterfaces
from mythos.players.player import PlayerInterfaceNotLoadedError
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode


_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")

_CATALOGS = RegistryBundle()
_CATALOGS.progress.register(NormalProgressNode("start", ("complete",), is_entry=True))
_CATALOGS.progress.register(NormalProgressNode("complete", ()))
_CATALOGS = _CATALOGS.freeze(_FILE_IDS)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _seed_player(session, player_id):
    session.add(
        PlayerProgress(
            player_id=player_id,
            version=1,
        )
    )


def _factory():
    return PlayerFactory(_CATALOGS, FakeObjectStore(), _FILE_IDS)


async def test_player_factory_create_does_not_load_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    assert player._progress is None
    assert player._artifacts is None
    assert player._accounts is None


async def test_player_accessing_uninitialized_progress_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="progress interface not loaded"):
        _ = player.progress


async def test_player_accessing_uninitialized_artifacts_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="artifacts interface not loaded"):
        _ = player.artifacts


async def test_player_accessing_uninitialized_accounts_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="accounts interface not loaded"):
        _ = player.accounts


async def test_player_load_progress_caches_and_returns_interface(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    progress = await player.load_progress()
    assert player._progress is progress
    assert player.progress is progress


async def test_player_load_artifacts_creates_empty_interface(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    artifacts = await player.load_artifacts()
    assert player._artifacts is artifacts
    assert player.artifacts is artifacts
    assert artifacts.tree_nodes() == ()


async def test_player_load_accounts_creates_empty_interface(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    accounts = await player.load_accounts()
    assert player._accounts is accounts
    assert accounts.accounts == ()


async def test_player_load_interfaces_loads_only_selected_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().create(session, player_id, writable=False)
    await player.load_interfaces(PlayerInterfaces.PROGRESS | PlayerInterfaces.ARTIFACTS)

    assert player._progress is not None
    assert player._artifacts is not None
    assert player._accounts is None


async def test_player_factory_load_initializes_both_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _factory().load(session, player_id, writable=False)
    assert player._progress is not None
    assert player._artifacts is not None
    assert player._accounts is not None
    assert player.progress.version == 1
    assert player.artifacts.tree_nodes() == ()
    assert player.accounts.accounts == ()


async def test_player_factory_load_unknown_player_raises(session) -> None:
    with pytest.raises(PlayerNotFoundError):
        await _factory().load(session, uuid4(), writable=False)
