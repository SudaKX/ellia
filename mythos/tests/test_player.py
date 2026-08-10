import mythos.commands  # noqa: F401  # ensure commands are loaded before loader to avoid circular import
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.anyio

from _helpers.object_store import FakeObjectStore
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerProgress, PlayerRecord
from mythos.players.loader import PlayerLoader, PlayerNotFoundError
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import PlayerInterfaceNotLoadedError, PlayerInterfaceVersionError
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
    session.add_all(
        (
            PlayerRecord(
                id=player_id,
                username=str(player_id),
                username_normalized=str(player_id),
            ),
            PlayerProgress(player_id=player_id, version=1),
        )
    )


def _loader():
    return PlayerLoader(_CATALOGS, FakeObjectStore(), _FILE_IDS)


async def test_player_loader_create_does_not_load_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    assert player._progress is None
    assert player._artifacts is None
    assert player._accounts is None
    assert player._credits is None
    assert player._hints is None


async def test_player_accessing_uninitialized_progress_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="progress interface not loaded"):
        _ = player.progress


async def test_player_accessing_uninitialized_artifacts_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="artifacts interface not loaded"):
        _ = player.artifacts


async def test_player_accessing_uninitialized_accounts_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="accounts interface not loaded"):
        _ = player.accounts


async def test_player_accessing_uninitialized_credits_and_hints_raises(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    with pytest.raises(PlayerInterfaceNotLoadedError, match="credits interface not loaded"):
        _ = player.credits
    with pytest.raises(PlayerInterfaceNotLoadedError, match="hints interface not loaded"):
        _ = player.hints


async def test_player_load_progress_caches_and_returns_interface(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    progress = await player.load_progress()
    assert player._progress is progress
    assert player.progress is progress


async def test_player_load_artifacts_creates_empty_interface(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    artifacts = await player.load_artifacts()
    assert player._artifacts is artifacts
    assert player.artifacts is artifacts
    assert artifacts.tree_nodes() == ()


async def test_player_load_accounts_creates_empty_interface(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    accounts = await player.load_accounts()
    assert player._accounts is accounts
    assert accounts.accounts == ()


async def test_player_load_credits_and_hints_creates_empty_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    credits = await player.load_credits()
    hints = await player.load_hints()
    assert player.credits is credits
    assert player.hints is hints
    assert credits.vtb == 0
    assert hints.disclosures == ()


async def test_player_load_interfaces_loads_only_selected_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    await player.load_interfaces(PlayerInterfaces.PROGRESS | PlayerInterfaces.ARTIFACTS)

    assert player._progress is not None
    assert player._artifacts is not None
    assert player._accounts is None
    assert player._credits is None
    assert player._hints is None


async def test_player_loader_load_initializes_both_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().load(session, player_id, writable=False)
    assert player._progress is not None
    assert player._artifacts is not None
    assert player._accounts is not None
    assert player._credits is not None
    assert player._hints is not None
    assert player.progress.version == 1
    assert player.artifacts.tree_nodes() == ()
    assert player.accounts.accounts == ()
    assert player.credits.vtb == 0
    assert player.hints.disclosures == ()


async def test_player_state_versions_require_versioned_loaded_interfaces(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=False)
    versioned_interfaces = (
        PlayerInterfaces.PROGRESS
        | PlayerInterfaces.ARTIFACTS
        | PlayerInterfaces.ACCOUNTS
        | PlayerInterfaces.CREDITS
    )
    await player.load_interfaces(versioned_interfaces)

    assert player.state_versions(versioned_interfaces) == {
        "progress": 1,
        "artifacts": 0,
        "accounts": 0,
        "credits": 0,
    }

    await player.load_hints()
    with pytest.raises(PlayerInterfaceVersionError, match="hints"):
        player.state_versions(PlayerInterfaces.HINTS)


async def test_player_owns_file_tree_cache_and_mutations_invalidate_it(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=True)
    await player.load_artifacts()
    await player.load_credits()
    first = player.get_file_tree(_CATALOGS.merged_files, "pft4_first")
    assert player.get_file_tree(_CATALOGS.merged_files, "pft4_second") is first

    await player.credits.grant_vtb(1)
    second = player.get_file_tree(_CATALOGS.merged_files, "pft4_third")
    assert second is not first

    player.invalidate_cache()
    assert player.get_file_tree(_CATALOGS.merged_files, "pft4_fourth") is not second


async def test_unrelated_credits_do_not_change_file_tree_version(session) -> None:
    player_id = uuid4()
    await _seed_player(session, player_id)
    await session.commit()

    player = await _loader().create(session, player_id, writable=True)
    await player.load_artifacts()
    await player.load_credits()
    version_before = _FILE_IDS.encode_player_tree_version(
        _CATALOGS.merged_files.resource_version,
        player.state_versions(PlayerInterfaces.ARTIFACTS),
    )
    await player.credits.grant_vtb(1)
    version_after = _FILE_IDS.encode_player_tree_version(
        _CATALOGS.merged_files.resource_version,
        player.state_versions(PlayerInterfaces.ARTIFACTS),
    )

    assert version_before.startswith("pft4_")
    assert version_after == version_before


async def test_player_loader_load_unknown_player_raises(session) -> None:
    with pytest.raises(PlayerNotFoundError):
        await _loader().load(session, uuid4(), writable=False)
