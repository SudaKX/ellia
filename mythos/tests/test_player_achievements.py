from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerAchievementState, PlayerRecord
from mythos.players.interfaces import PlayerInterfaces, ReadOnlyAchievementError
from mythos.players.loader import PlayerLoader
from mythos.registry.bundle import RegistryBundle


pytestmark = pytest.mark.anyio

_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with session_factory() as current:
        yield current
    await engine.dispose()


async def _seed_player(session):
    player_id = uuid4()
    session.add(PlayerRecord(id=player_id, username="achievement-player", username_normalized="achievement-player"))
    await session.commit()
    return player_id


def _loader() -> PlayerLoader:
    return PlayerLoader(RegistryBundle().freeze(_FILE_IDS), FakeObjectStore(), _FILE_IDS)


async def test_achievement_interface_is_idempotent_and_read_only(session) -> None:
    player_id = await _seed_player(session)
    loader = _loader()

    readonly = await loader.load(session, player_id, writable=False, interfaces=PlayerInterfaces.ACHIEVEMENTS)
    assert readonly.achievements.states == ()
    with pytest.raises(ReadOnlyAchievementError):
        await readonly.achievements.earn("test.achievement")

    player = await loader.load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
    first = await player.achievements.earn("test.achievement")
    second = await player.achievements.earn("test.achievement")
    assert first == second
    assert first.status == "available"
    claimed = await player.achievements.claim("test.achievement")
    repeated = await player.achievements.claim("test.achievement")
    assert claimed is not None and claimed.status == "claimed"
    assert repeated == claimed
    await session.commit()

    stored = await session.get(PlayerAchievementState, (player_id, "test.achievement"))
    assert stored is not None and stored.claimed_at is not None


async def test_achievement_state_cascades_when_player_is_deleted(session) -> None:
    player_id = await _seed_player(session)
    player = await _loader().load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
    await player.achievements.earn("test.achievement")
    await session.commit()

    await session.delete(await session.get(PlayerRecord, player_id))
    await session.commit()

    assert await session.scalar(
        select(PlayerAchievementState.player_id).where(PlayerAchievementState.player_id == player_id)
    ) is None
