from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerAchievementState, PlayerRecord
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.loader import PlayerLoader
from mythos.registry.achievements import AchievementDefinition
from mythos.registry.bundle import RegistryBundle
from mythos.registry.callbacks import module_handler
from mythos.services.achievements import (
    AchievementDeletedError,
    AchievementService,
    AchievementStatus,
)


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
    session.add(PlayerRecord(id=player_id, username="achievement-service", username_normalized="achievement-service"))
    await session.commit()
    return player_id


def _setup(*definitions: AchievementDefinition, fallbacks=()):
    registries = RegistryBundle()
    for definition in definitions:
        registries.achievements.register(definition)
    for stable_id, meta, immediate in fallbacks:
        registries.achievements.set_fallback(stable_id, meta, immediate)
    catalogs = registries.freeze(_FILE_IDS)
    return catalogs, PlayerLoader(catalogs, FakeObjectStore(), _FILE_IDS), AchievementService(
        catalogs.achievements,
        _FILE_IDS,
    )


async def test_service_check_is_idempotent_and_immediate_effect_claims(session) -> None:
    effects: list[str] = []

    @module_handler("test.service")(1, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        return True

    @module_handler("test.service")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        effects.append("ran")

    catalogs, loader, service = _setup(
        AchievementDefinition("test.immediate", True, {"title": "Immediate"}, condition, effect)
    )
    player_id = await _seed_player(session)

    async with session.begin():
        player = await loader.load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
        first = await service.check(player)
    assert first.earned_stable_ids == ("test.immediate",)

    async with session.begin():
        player = await loader.load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
        second = await service.check(player)
        await service.apply_effects(player, second.effect_stable_ids)
    assert second.earned_stable_ids == ()
    assert effects == ["ran"]

    async with session.begin():
        player = await loader.load(session, player_id, writable=False, interfaces=PlayerInterfaces.ACHIEVEMENTS)
        snapshot = service.snapshots(player)[0]
    assert snapshot.status == AchievementStatus.CLAIMED
    assert snapshot.body()["public_id"] == catalogs.achievements.public_id_for("test.immediate")


async def test_service_rolls_back_failed_effect_but_keeps_earned_state(session) -> None:
    @module_handler("test.service.failure")(1, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        return True

    @module_handler("test.service.failure")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        raise RuntimeError("expected effect failure")

    _catalogs, loader, service = _setup(
        AchievementDefinition("test.failure", True, {}, condition, effect)
    )
    player_id = await _seed_player(session)

    async with session.begin():
        player = await loader.load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
        result = await service.check(player)
    with pytest.raises(RuntimeError, match="expected effect failure"):
        async with session.begin():
            player = await loader.load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
            await service.apply_effects(player, result.effect_stable_ids)

    async with session.begin():
        state = await session.get(PlayerAchievementState, (player_id, "test.failure"))
    assert state is not None and state.claimed_at is None


async def test_service_distinguishes_deleted_and_missing_fallback_states(session) -> None:
    player_id = await _seed_player(session)
    session.add_all(
        [
            PlayerAchievementState(player_id=player_id, achievement_stable_id="test.deleted", earned_at=datetime.now(UTC)),
            PlayerAchievementState(player_id=player_id, achievement_stable_id="test.missing", earned_at=datetime.now(UTC)),
        ]
    )
    await session.commit()
    _catalogs, loader, service = _setup(
        fallbacks=(("test.deleted", {"title": "Old"}, False),),
    )

    async with session.begin():
        player = await loader.load(session, player_id, writable=False, interfaces=PlayerInterfaces.ACHIEVEMENTS)
        snapshots = {item.stable_id: item for item in service.snapshots(player)}
    assert snapshots["test.deleted"].status == AchievementStatus.DELETED
    assert snapshots["test.missing"].status == AchievementStatus.MISSING_FALLBACK
    assert snapshots["test.missing"].meta == {}
    with pytest.raises(AchievementDeletedError):
        await service.claim(player, snapshots["test.deleted"].public_id)


async def test_service_skips_grant_only_achievements_and_orders_immediate_candidates(session) -> None:
    effects: list[str] = []

    @module_handler("test.service.grant-only")(1, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        effects.append("ran")

    @module_handler("test.service.grant-only")(2, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        return True

    _catalogs, loader, service = _setup(
        AchievementDefinition("test.condition", True, {}, condition, effect),
        AchievementDefinition("test.grant-only", True, {}, None, effect),
    )
    player_id = await _seed_player(session)

    async with session.begin():
        player = await loader.load(session, player_id, writable=True, interfaces=PlayerInterfaces.ACHIEVEMENTS)
        result = await service.check(player)
        assert result.checked_count == 1
        assert result.earned_stable_ids == ("test.condition",)
        assert service.immediate_effect_candidates(("test.grant-only", "test.condition", "test.condition")) == (
            "test.condition",
            "test.grant-only",
        )
    assert effects == []
