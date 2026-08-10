from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.players.player import Player


PipelineResult = TypeVar("PipelineResult")
PipelineOperation: TypeAlias = Callable[[AsyncSession, Player], Awaitable[PipelineResult]]
PipelinePhase: TypeAlias = Callable[[AsyncSession, Player], Awaitable[None]]
PipelineHook: TypeAlias = Callable[[AsyncSession, Player], Awaitable[None]]


class PipelinedTransaction:
    """Run one Player operation and its post-operation transaction stages."""

    def __init__(
        self,
        *,
        post_operation_phases: tuple[PipelinePhase, ...] = (),
        pre_commit_hooks: tuple[PipelineHook, ...] = (),
    ) -> None:
        self._post_operation_phases = post_operation_phases
        self._pre_commit_hooks = pre_commit_hooks

    async def run(
        self,
        session: AsyncSession,
        player: Player,
        operation: PipelineOperation[PipelineResult],
    ) -> PipelineResult:
        result = await operation(session, player)
        for phase in self._post_operation_phases:
            await phase(session, player)
        for hook in self._pre_commit_hooks:
            await hook(session, player)
        return result
