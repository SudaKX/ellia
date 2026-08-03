from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import CommandTransactionExecutor, RequestCache, ResponseSpec
from mythos.persistence.base import Base
from mythos.players.factory import PlayerFactory
from mythos.players.interface_selection import PlayerInterfaces
from mythos.players.player import Player


pytestmark = pytest.mark.anyio


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def test_executor_loads_default_interfaces_runs_hooks_and_replays(session) -> None:
    player_id = uuid4()
    player = Mock(spec=Player)
    player.load_interfaces = AsyncMock()
    factory = Mock(spec=PlayerFactory)
    factory.create = AsyncMock(return_value=player)
    hook = AsyncMock()
    executor = CommandTransactionExecutor(factory, RequestCache(maxsize=4, ttl_seconds=60), (hook,))

    async def command(context) -> ResponseSpec:
        assert context.player is player
        return ResponseSpec(status_code=200, body={"ok": True}, headers={})

    request_id = uuid4()
    result = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        request_id,
        command,
    )
    replayed = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        request_id,
        command,
    )

    assert result.response.body == {"content": {"ok": True}, "followups": []}
    assert replayed is result
    factory.create.assert_awaited_once_with(session, player_id, writable=True)
    player.load_interfaces.assert_awaited_once_with(PlayerInterfaces.ALL)
    hook.assert_awaited_once_with(session, player)


async def test_executor_nocache_uses_existing_transaction_and_can_skip_hooks(session) -> None:
    player_id = uuid4()
    player = Mock(spec=Player)
    player.load_interfaces = AsyncMock()
    factory = Mock(spec=PlayerFactory)
    factory.create = AsyncMock(return_value=player)
    hook = AsyncMock()
    executor = CommandTransactionExecutor(factory, RequestCache(maxsize=4, ttl_seconds=60), (hook,))
    seen: list[Player] = []

    async def operation(loaded_player: Player) -> None:
        seen.append(loaded_player)

    await executor.execute_nocache(
        session,
        player_id,
        operation,
        interfaces=PlayerInterfaces.ARTIFACTS,
    )
    player.load_interfaces.assert_awaited_once_with(PlayerInterfaces.ARTIFACTS)
    hook.assert_awaited_once_with(session, player)

    player.load_interfaces.reset_mock()
    hook.reset_mock()
    async with session.begin():
        await executor.execute_nocache_itx(
            session,
            player_id,
            operation,
            interfaces=PlayerInterfaces.ACCOUNTS,
            run_pre_commit_hooks=False,
        )

    assert seen == [player, player]
    player.load_interfaces.assert_awaited_once_with(PlayerInterfaces.ACCOUNTS)
    hook.assert_not_awaited()
