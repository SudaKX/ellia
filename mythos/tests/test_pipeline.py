from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mythos.commands.pipeline import PipelinedTransaction
from mythos.persistence.base import Base
from mythos.players.player import Player


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


async def test_pipeline_runs_operation_phases_and_hooks_in_order(session) -> None:
    events: list[str] = []
    player = Mock(spec=Player)

    async def operation(_session, _player):
        events.append("operation")
        return "result"

    async def phase(_session, _player) -> None:
        events.append("phase")

    async def hook(_session, _player) -> None:
        events.append("hook")

    pipeline = PipelinedTransaction(
        post_operation_phases=(phase,),
        pre_commit_hooks=(hook,),
    )

    async with session.begin():
        result = await pipeline.run(session, player, operation)

    assert result == "result"
    assert events == ["operation", "phase", "hook"]


async def test_pipeline_does_not_run_later_stages_after_failure(session) -> None:
    phase = AsyncMock(side_effect=RuntimeError("phase failed"))
    hook = AsyncMock()
    pipeline = PipelinedTransaction(
        post_operation_phases=(phase,),
        pre_commit_hooks=(hook,),
    )

    with pytest.raises(RuntimeError, match="phase failed"):
        async with session.begin():
            await pipeline.run(session, Mock(spec=Player), AsyncMock(return_value=None))

    phase.assert_awaited_once()
    hook.assert_not_awaited()
