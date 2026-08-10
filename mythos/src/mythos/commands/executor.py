from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.commands.cache import RequestCache
from mythos.commands.models import CachedResponse, ResponseSpec
from mythos.commands.pipeline import PipelinedTransaction
from mythos.players.context import CommandContext
from mythos.players.loader import PlayerLoader
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player

if TYPE_CHECKING:
    from mythos.services.tasks.service import TaskService, TaskRunReport


class EndpointCommandExecutor:
    def __init__(
        self,
        player_loader: PlayerLoader,
        request_cache: RequestCache,
        pipelined_transaction: PipelinedTransaction,
        task_service: TaskService | None = None,
    ) -> None:
        self._player_loader = player_loader
        self._request_cache = request_cache
        self._task_service = task_service
        self._pipeline = pipelined_transaction

    async def execute(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        operation: Callable[[CommandContext], Awaitable[ResponseSpec]],
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
        run_task_phase: bool = True,
    ) -> CachedResponse:
        with self._request_cache.lease(request_id, identity.player_id) as lease:
            if lease.replay is not None:
                return lease.replay
            if run_task_phase:
                async with session.begin():
                    await self._run_tasks_itx(session, identity.player_id)
            async with session.begin():
                completed = await self._execute_operation_itx(
                    session,
                    identity,
                    request_id,
                    operation,
                    interfaces=interfaces,
                )
            lease.complete(completed)
            return completed

    async def _run_tasks_itx(self, session: AsyncSession, player_id: UUID) -> TaskRunReport:
        if self._task_service is None:
            raise RuntimeError("Task execution is not configured.")
        return await self._task_service.run_itx(session, player_id)

    async def _execute_operation_itx(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        operation: Callable[[CommandContext], Awaitable[ResponseSpec]],
        *,
        interfaces: PlayerInterfaces,
    ) -> CachedResponse:
        player = await self._load_player(
            session,
            identity.player_id,
            interfaces=interfaces,
            writable=True,
        )
        context = CommandContext(
            identity=identity,
            player=player,
            request_id=request_id,
        )
        async def command_operation(_session: AsyncSession, _player: Player) -> ResponseSpec:
            return await operation(context)

        response = await self._pipeline.run(session, player, command_operation)
        return CachedResponse(
            owner_player_id=identity.player_id,
            response=ResponseSpec(
                status_code=response.status_code,
                body={
                    "content": response.body,
                    "followups": context._freeze_followups(),
                },
                headers=response.headers,
            ),
        )

    async def _load_player(
        self,
        session: AsyncSession,
        player_id: UUID,
        *,
        interfaces: PlayerInterfaces,
        writable: bool,
    ) -> Player:
        if writable:
            return await self._player_loader.load_writable(session, player_id, interfaces=interfaces)
        return await self._player_loader.load_readonly(session, player_id, interfaces=interfaces)


class TaskCommandExecutor:
    """Adapt the transaction-neutral TaskService to the task HTTP endpoint."""

    def __init__(self, task_service: TaskService, request_cache: RequestCache) -> None:
        self._task_service = task_service
        self._request_cache = request_cache

    async def execute(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
    ) -> CachedResponse:
        with self._request_cache.lease(request_id, identity.player_id) as lease:
            if lease.replay is not None:
                return lease.replay
            async with session.begin():
                report = await self._task_service.run_itx(session, identity.player_id)
                response = self._response(identity.player_id, report)
            lease.complete(response)
            return response

    @staticmethod
    def _response(player_id: UUID, report: TaskRunReport) -> CachedResponse:
        return CachedResponse(
            owner_player_id=player_id,
            response=ResponseSpec(
                status_code=200,
                body={"content": report.body(), "followups": []},
                headers={},
            ),
        )
