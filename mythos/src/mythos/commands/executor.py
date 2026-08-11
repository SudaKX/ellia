from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.commands.cache import RequestCache
from mythos.commands.models import CachedResponse, ResponseSpec
from mythos.commands.pipeline import PipelinedTransaction
from mythos.core.followups import ContextScope
from mythos.players.context import CommandContext
from mythos.players.loader import PlayerLoader
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.services.tasks.service import TaskHandlerFailure, TaskRunReport, TaskService


@dataclass(frozen=True, slots=True)
class _TaskPhaseResult:
    report: TaskRunReport | None = None
    failure: TaskHandlerFailure | None = None


async def _run_task_phase(
    session: AsyncSession,
    player_loader: PlayerLoader,
    task_service: TaskService,
    pipeline: PipelinedTransaction,
    player_id: UUID,
    scope: ContextScope,
) -> _TaskPhaseResult:
    player = await player_loader.load_writable(
        session,
        player_id,
        interfaces=PlayerInterfaces.TASKS,
    )
    report: TaskRunReport | None = None
    failure: TaskHandlerFailure | None = None
    try:
        async with session.begin_nested():
            async def task_operation(_session: AsyncSession, current_player: Player) -> TaskRunReport:
                return await task_service.run_loaded(_session, current_player, scope)

            report = await pipeline.run(session, player, task_operation)
    except TaskHandlerFailure as error:
        await task_service.record_handler_failure(session, error.player_id, error.task_id)
        failure = error
    return _TaskPhaseResult(report=report, failure=failure)


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
            scope = ContextScope.http()
            task_result: _TaskPhaseResult | None = None
            if run_task_phase:
                async with session.begin():
                    task_result = await self._run_tasks_itx(session, identity.player_id, scope)
                if task_result.failure is not None:
                    raise task_result.failure
            async with session.begin():
                completed = await self._execute_operation_itx(
                    session,
                    identity,
                    request_id,
                    operation,
                    scope=scope,
                    interfaces=interfaces,
                )
            lease.complete(completed)
            return completed

    async def _run_tasks_itx(
        self,
        session: AsyncSession,
        player_id: UUID,
        scope: ContextScope,
    ) -> _TaskPhaseResult:
        if self._task_service is None:
            raise RuntimeError("Task execution is not configured.")
        return await _run_task_phase(
            session,
            self._player_loader,
            self._task_service,
            self._pipeline,
            player_id,
            scope,
        )

    async def _execute_operation_itx(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        operation: Callable[[CommandContext], Awaitable[ResponseSpec]],
        *,
        scope: ContextScope,
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
            scope=scope,
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
                    "followups": scope.to_json(),
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

    def __init__(
        self,
        player_loader: PlayerLoader,
        task_service: TaskService,
        request_cache: RequestCache,
        pipeline: PipelinedTransaction,
    ) -> None:
        self._player_loader = player_loader
        self._task_service = task_service
        self._request_cache = request_cache
        self._pipeline = pipeline

    async def execute(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
    ) -> CachedResponse:
        with self._request_cache.lease(request_id, identity.player_id) as lease:
            if lease.replay is not None:
                return lease.replay
            scope = ContextScope.http()
            task_result: _TaskPhaseResult
            async with session.begin():
                task_result = await _run_task_phase(
                    session,
                    self._player_loader,
                    self._task_service,
                    self._pipeline,
                    identity.player_id,
                    scope,
                )
            if task_result.failure is not None:
                raise task_result.failure
            if task_result.report is None:
                raise RuntimeError("Task phase completed without a report.")
            response = self._response(identity.player_id, task_result.report, scope)
            lease.complete(response)
            return response

    @staticmethod
    def _response(
        player_id: UUID,
        report: TaskRunReport,
        scope: ContextScope,
    ) -> CachedResponse:
        return CachedResponse(
            owner_player_id=player_id,
            response=ResponseSpec(
                status_code=200,
                body={
                    "content": report.body(),
                    "followups": scope.to_json(),
                },
                headers={},
            ),
        )
