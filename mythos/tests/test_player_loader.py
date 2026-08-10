from __future__ import annotations

from uuid import uuid4
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerRecord
from mythos.players.loader import PlayerLoader, PlayerNotFoundError
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.bundle import RegistryBundle


pytestmark = pytest.mark.anyio


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as current:
        yield current
    await engine.dispose()


async def _seed_player(session) -> object:
    player_id = uuid4()
    session.add(PlayerRecord(id=player_id, username="player-session", username_normalized="player-session"))
    await session.commit()
    return player_id


_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


def _loader() -> tuple[PlayerLoader, Mock]:
    player = Mock(spec=Player)
    player.load_interfaces = AsyncMock()
    loader = PlayerLoader(RegistryBundle().freeze(_FILE_IDS), FakeObjectStore(), _FILE_IDS)
    loader.create = AsyncMock(return_value=player)
    return loader, player


async def test_session_begin_commits_and_rolls_back(session) -> None:
    committed_id = uuid4()
    async with session.begin():
        session.add(
            PlayerRecord(
                id=committed_id,
                username="committed-player",
                username_normalized="committed-player",
            )
        )
    assert await session.get(PlayerRecord, committed_id) is not None
    await session.rollback()

    rolled_back_id = uuid4()
    with pytest.raises(RuntimeError, match="rollback"):
        async with session.begin():
            session.add(
                PlayerRecord(
                    id=rolled_back_id,
                    username="rolled-back-player",
                    username_normalized="rolled-back-player",
                )
            )
            raise RuntimeError("rollback")
    assert await session.get(PlayerRecord, rolled_back_id) is None


async def test_player_loader_rejects_missing_players(session) -> None:
    loader, _player = _loader()

    with pytest.raises(PlayerNotFoundError):
        await loader.load_readonly(session, uuid4(), interfaces=PlayerInterfaces.NONE)
    with pytest.raises(PlayerNotFoundError):
        await loader.lock_player(session, uuid4())


async def test_player_loader_loads_readonly_and_writable_players(session) -> None:
    player_id = await _seed_player(session)
    loader, player = _loader()

    readonly = await loader.load_readonly(
        session,
        player_id,
        interfaces=PlayerInterfaces.PROGRESS,
    )
    writable = await loader.load_writable(
        session,
        player_id,
        interfaces=PlayerInterfaces.CREDITS,
    )

    assert readonly is player
    assert writable is player
    assert loader.create.await_args_list[0].kwargs == {"writable": False}
    assert loader.create.await_args_list[1].kwargs == {"writable": True}
    assert player.load_interfaces.await_args_list[0].args == (PlayerInterfaces.PROGRESS,)
    assert player.load_interfaces.await_args_list[1].args == (PlayerInterfaces.CREDITS,)


async def test_player_loader_reload_creates_a_fresh_writable_aggregate(session) -> None:
    player_id = await _seed_player(session)
    first = Mock(spec=Player)
    first.load_interfaces = AsyncMock()
    second = Mock(spec=Player)
    second.load_interfaces = AsyncMock()
    loader = PlayerLoader(RegistryBundle().freeze(_FILE_IDS), FakeObjectStore(), _FILE_IDS)
    loader.create = AsyncMock(side_effect=(first, second))

    loaded = await loader.load_writable(session, player_id, interfaces=PlayerInterfaces.NONE)
    reloaded = await loader.reload(session, player_id, interfaces=PlayerInterfaces.NONE)

    assert loaded is first
    assert reloaded is second
    assert loader.create.await_count == 2


async def test_player_loader_can_query_the_loaded_player(session) -> None:
    player_id = await _seed_player(session)
    loader, _player = _loader()

    await loader.load_readonly(session, player_id, interfaces=PlayerInterfaces.NONE)

    assert await session.scalar(select(PlayerRecord.id).where(PlayerRecord.id == player_id)) == player_id
