from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import PlayerIdentity
from mythos.commands import (
    AchievementCommandExecutor,
    EndpointCommandExecutor,
    PipelinedTransaction,
    RequestCache,
    ResponseSpec,
)
from mythos.core.file_ids import FileIdCodec
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerAchievementState, PlayerProgress, PlayerRecord
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.loader import PlayerLoader
from mythos.registry.achievements import AchievementDefinition
from mythos.registry.bundle import RegistryBundle
from mythos.registry.callbacks import module_handler
from mythos.services.achievements import AchievementService


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
    session.add_all(
        [
            PlayerRecord(id=player_id, username="achievement-executor", username_normalized="achievement-executor"),
            PlayerProgress(player_id=player_id, version=1),
        ]
    )
    await session.commit()
    return player_id


def _runtime(definition: AchievementDefinition):
    registries = RegistryBundle()
    registries.achievements.register(definition)
    catalogs = registries.freeze(_FILE_IDS)
    loader = PlayerLoader(catalogs, FakeObjectStore(), _FILE_IDS)
    service = AchievementService(catalogs.achievements, _FILE_IDS)
    return loader, service


async def test_endpoint_executor_runs_check_and_effect_after_operation_and_replays(session) -> None:
    effects: list[str] = []

    @module_handler("test.executor")(1, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        return True

    @module_handler("test.executor")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        effects.append("effect")

    loader, service = _runtime(AchievementDefinition("test.after-operation", True, {}, condition, effect))
    player_id = await _seed_player(session)
    executor = EndpointCommandExecutor(
        loader,
        RequestCache(maxsize=8, ttl_seconds=60),
        PipelinedTransaction(),
        achievement_service=service,
    )
    request_id = uuid4()

    async def operation(_context) -> ResponseSpec:
        return ResponseSpec(status_code=200, body={"ok": True}, headers={})

    result = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        request_id,
        operation,
        run_task_phase=False,
    )
    replay = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        request_id,
        operation,
        run_task_phase=False,
    )

    assert result.response.body == {"content": {"ok": True}, "followups": []}
    assert replay is result
    assert effects == ["effect"]
    state = await session.get(PlayerAchievementState, (player_id, "test.after-operation"))
    assert state is not None and state.claimed_at is not None


async def test_endpoint_executor_preserves_operation_response_when_check_fails(session) -> None:
    @module_handler("test.executor.failure")(1, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        raise RuntimeError("condition failure")

    @module_handler("test.executor.failure")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        raise AssertionError("effect must not run")

    loader, service = _runtime(AchievementDefinition("test.check-failure", True, {}, condition, effect))
    player_id = await _seed_player(session)
    executor = EndpointCommandExecutor(
        loader,
        RequestCache(maxsize=8, ttl_seconds=60),
        PipelinedTransaction(),
        achievement_service=service,
    )

    async def operation(_context) -> ResponseSpec:
        return ResponseSpec(status_code=201, body={"created": True}, headers={})

    result = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        uuid4(),
        operation,
        run_task_phase=False,
    )

    assert result.response.status_code == 201
    assert result.response.body["content"] == {"created": True}
    assert result.response.body["warn"][0]["code"] == "achievement-check-failed"
    assert await session.get(PlayerAchievementState, (player_id, "test.check-failure")) is None


async def test_endpoint_executor_drains_proactive_grants_and_deduplicates_effect_batch(session) -> None:
    calls: list[str] = []

    @module_handler("test.executor.grant")(1, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        return True

    @module_handler("test.executor.grant")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        calls.append("effect")

    loader, service = _runtime(AchievementDefinition("test.proactive", True, {}, condition, effect))
    player_id = await _seed_player(session)
    executor = EndpointCommandExecutor(
        loader,
        RequestCache(maxsize=8, ttl_seconds=60),
        PipelinedTransaction(),
        achievement_service=service,
    )

    async def operation(context) -> ResponseSpec:
        await context.player.achievements.grant("test.proactive")
        assert calls == []
        return ResponseSpec(status_code=200, body={"ok": True}, headers={})

    result = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        uuid4(),
        operation,
        run_task_phase=False,
    )

    assert result.response.body == {"content": {"ok": True}, "followups": []}
    assert calls == ["effect"]
    state = await session.get(PlayerAchievementState, (player_id, "test.proactive"))
    assert state is not None and state.claimed_at is not None


async def test_endpoint_executor_applies_proactive_grant_after_failed_check(session) -> None:
    calls: list[str] = []

    @module_handler("test.executor.grant-failure")(1, dependencies=PlayerInterfaces.NONE)
    def failing_condition(_player) -> bool:
        raise RuntimeError("condition failure")

    @module_handler("test.executor.grant-failure")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        calls.append("effect")

    loader, service = _runtime(
        AchievementDefinition("test.check-failure", True, {}, failing_condition, effect),
    )
    registries = RegistryBundle()
    registries.achievements.register(AchievementDefinition("test.check-failure", True, {}, failing_condition, effect))
    registries.achievements.register(AchievementDefinition("test.proactive", True, {}, None, effect))
    catalogs = registries.freeze(_FILE_IDS)
    loader = PlayerLoader(catalogs, FakeObjectStore(), _FILE_IDS)
    service = AchievementService(catalogs.achievements, _FILE_IDS)
    player_id = await _seed_player(session)
    executor = EndpointCommandExecutor(
        loader,
        RequestCache(maxsize=8, ttl_seconds=60),
        PipelinedTransaction(),
        achievement_service=service,
    )

    async def operation(context) -> ResponseSpec:
        await context.player.achievements.grant("test.proactive")
        return ResponseSpec(status_code=201, body={"created": True}, headers={})

    result = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        uuid4(),
        operation,
        run_task_phase=False,
    )

    assert result.response.body["warn"][0]["code"] == "achievement-check-failed"
    assert calls == ["effect"]
    proactive = await session.get(PlayerAchievementState, (player_id, "test.proactive"))
    failed_check = await session.get(PlayerAchievementState, (player_id, "test.check-failure"))
    assert proactive is not None and proactive.claimed_at is not None
    assert failed_check is None


async def test_achievement_command_executor_check_claim_and_replay_without_tasks(session) -> None:
    effects: list[str] = []

    @module_handler("test.command")(1, dependencies=PlayerInterfaces.NONE)
    def condition(_player) -> bool:
        return True

    @module_handler("test.command")(2, dependencies=PlayerInterfaces.NONE)
    async def effect(_player) -> None:
        effects.append("effect")

    loader, service = _runtime(AchievementDefinition("test.manual", False, {}, condition, effect))
    player_id = await _seed_player(session)
    executor = AchievementCommandExecutor(
        loader,
        service,
        RequestCache(maxsize=8, ttl_seconds=60),
        PipelinedTransaction(),
    )
    identity = PlayerIdentity(player_id=player_id)
    check_id = uuid4()
    checked = await executor.check(session, identity, check_id)
    assert checked.response.body["content"]["check"]["earned"]
    assert effects == []

    public_id = service.catalog.public_id_for("test.manual")
    claim_id = uuid4()
    claimed = await executor.claim(session, identity, claim_id, public_id)
    replay = await executor.claim(session, identity, claim_id, public_id)
    assert claimed.response.body["content"]["achievement"]["status"] == "claimed"
    assert replay is claimed
    assert effects == ["effect"]
