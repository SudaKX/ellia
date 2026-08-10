from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mythos.auth.tokens import PlayerIdentity
from mythos.commands import EndpointCommandExecutor, PipelinedTransaction, RequestCache, ResponseSpec
from mythos.persistence.models import PlayerRecord
from mythos.persistence.base import Base
from mythos.players.loader import PlayerLoader
from mythos.players.interfaces import PlayerInterfaces
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
    session.add(PlayerRecord(id=player_id, username="command-player", username_normalized="command-player"))
    await session.commit()
    player = Mock(spec=Player)
    player.load_interfaces = AsyncMock()
    loader = Mock(spec=PlayerLoader)
    loader.load_writable = AsyncMock(return_value=player)
    hook = AsyncMock()
    executor = EndpointCommandExecutor(
        loader,
        RequestCache(maxsize=4, ttl_seconds=60),
        PipelinedTransaction(pre_commit_hooks=(hook,)),
    )

    async def command(context) -> ResponseSpec:
        assert context.player is player
        return ResponseSpec(status_code=200, body={"ok": True}, headers={})

    request_id = uuid4()
    result = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        request_id,
        command,
        run_task_phase=False,
    )
    replayed = await executor.execute(
        session,
        PlayerIdentity(player_id=player_id),
        request_id,
        command,
        run_task_phase=False,
    )

    assert result.response.body == {"content": {"ok": True}, "followups": []}
    assert replayed is result
    loader.load_writable.assert_awaited_once_with(session, player_id, interfaces=PlayerInterfaces.ALL)
    hook.assert_awaited_once_with(session, player)


async def test_endpoint_loader_is_reusable_across_transactions(session) -> None:
    player_id = uuid4()
    session.add(PlayerRecord(id=player_id, username="nocache-player", username_normalized="nocache-player"))
    await session.commit()
    player = Mock(spec=Player)
    player.load_interfaces = AsyncMock()
    loader = Mock(spec=PlayerLoader)
    loader.load_writable = AsyncMock(side_effect=(player, player))
    seen: list[Player] = []

    async def operation(loaded_player: Player) -> None:
        seen.append(loaded_player)

    async with session.begin():
        player = await loader.load_writable(session, player_id, interfaces=PlayerInterfaces.ARTIFACTS)
        await operation(player)

    async with session.begin():
        player = await loader.load_writable(session, player_id, interfaces=PlayerInterfaces.ACCOUNTS)
        await operation(player)

    assert len(seen) == 2
    assert loader.load_writable.await_args_list[0].kwargs == {"interfaces": PlayerInterfaces.ARTIFACTS}
    assert loader.load_writable.await_args_list[1].kwargs == {"interfaces": PlayerInterfaces.ACCOUNTS}
