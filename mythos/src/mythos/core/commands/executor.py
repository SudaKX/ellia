from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, TypeAlias
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands.cache import RequestCache
from mythos.core.commands.models import CachedResponse, ResponseSpec
from mythos.persistence.models import PlayerRecord
from mythos.players.context import CommandContext
from mythos.players.factory import PlayerFactory
from mythos.players.interface_selection import PlayerInterfaces
from mythos.players.player import Player

if TYPE_CHECKING:
    from mythos.services.tasks.executor import TaskExecutor, TaskRunReport

CommandPreCommitHook: TypeAlias = Callable[[AsyncSession, Player], Awaitable[None]]
NoCacheOperation: TypeAlias = Callable[[Player], Awaitable[None]]


class CommandTransactionExecutor:
    def __init__(
        self,
        player_factory: PlayerFactory,
        request_cache: RequestCache,
        pre_commit_hooks: tuple[CommandPreCommitHook, ...] = (),
        task_executor: TaskExecutor | None = None,
    ) -> None:
        self._player_factory = player_factory
        self._request_cache = request_cache
        self._pre_commit_hooks = pre_commit_hooks
        self._task_executor = task_executor

    async def execute(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        operation: Callable[[CommandContext], Awaitable[ResponseSpec]],
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
    ) -> CachedResponse:
        cached_response = self._request_cache.reserve(request_id, identity.player_id)
        if cached_response is not None:
            return cached_response

        try:
            async with session.begin():
                completed = await self._execute_operation_itx(
                    session,
                    identity,
                    request_id,
                    operation,
                    interfaces=interfaces,
                )
        except BaseException:
            self._request_cache.release(request_id)
            raise

        self._request_cache.complete(request_id, completed)
        return completed

    async def execute_with_task(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        operation: Callable[[CommandContext], Awaitable[ResponseSpec]],
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
    ) -> CachedResponse:
        cached_response = self._request_cache.reserve(request_id, identity.player_id)
        if cached_response is not None:
            return cached_response
        if self._task_executor is None:
            self._request_cache.release(request_id)
            raise RuntimeError("Task execution is not configured.")

        try:
            async with session.begin():
                await self._task_executor.run_itx(session, identity.player_id)
            async with session.begin():
                completed = await self._execute_operation_itx(
                    session,
                    identity,
                    request_id,
                    operation,
                    interfaces=interfaces,
                )
        except BaseException:
            self._request_cache.release(request_id)
            raise

        self._request_cache.complete(request_id, completed)
        return completed

    async def execute_tasks(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
    ) -> CachedResponse:
        cached_response = self._request_cache.reserve(request_id, identity.player_id)
        if cached_response is not None:
            return cached_response
        if self._task_executor is None:
            self._request_cache.release(request_id)
            raise RuntimeError("Task execution is not configured.")

        try:
            async with session.begin():
                report = await self._task_executor.run_itx(session, identity.player_id)
                completed = self._task_response(identity.player_id, report)
        except BaseException:
            self._request_cache.release(request_id)
            raise

        self._request_cache.complete(request_id, completed)
        return completed

    async def execute_tasks_nocache(self, session: AsyncSession, player_id: UUID) -> TaskRunReport:
        async with session.begin():
            return await self.execute_tasks_nocache_itx(session, player_id)

    async def execute_tasks_nocache_itx(self, session: AsyncSession, player_id: UUID) -> TaskRunReport:
        if self._task_executor is None:
            raise RuntimeError("Task execution is not configured.")
        return await self._task_executor.run_itx(session, player_id)

    async def execute_nocache(
        self,
        session: AsyncSession,
        player_id: UUID,
        operation: NoCacheOperation,
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
        run_pre_commit_hooks: bool = True,
        run_task_phase: bool = False,
    ) -> None:
        async with session.begin():
            await self.execute_nocache_itx(
                session,
                player_id,
                operation,
                interfaces=interfaces,
                run_pre_commit_hooks=run_pre_commit_hooks,
                run_task_phase=run_task_phase,
            )

    async def execute_nocache_itx(
        self,
        session: AsyncSession,
        player_id: UUID,
        operation: NoCacheOperation,
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
        run_pre_commit_hooks: bool = True,
        run_task_phase: bool = False,
    ) -> None:
        if run_task_phase:
            if self._task_executor is None:
                raise RuntimeError("Task execution is not configured.")
            await self._task_executor.run_itx(session, player_id)
        player = await self._load_player(
            session,
            player_id,
            interfaces=interfaces,
            writable=True,
        )
        await operation(player)
        if run_pre_commit_hooks:
            for hook in self._pre_commit_hooks:
                await hook(session, player)

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
        response = await operation(context)
        for hook in self._pre_commit_hooks:
            await hook(session, player)
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

    @staticmethod
    def _task_response(player_id: UUID, report: TaskRunReport) -> CachedResponse:
        return CachedResponse(
            owner_player_id=player_id,
            response=ResponseSpec(
                status_code=200,
                body={"content": report.body(), "followups": []},
                headers={},
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
            # Lock the player row before loading mutable interface state.
            await session.execute(
                update(PlayerRecord)
                .where(PlayerRecord.id == player_id)
                .values(last_accessed_at=PlayerRecord.last_accessed_at)
            )
        player = await self._player_factory.create(session, player_id, writable=writable)
        await player.load_interfaces(interfaces)
        return player
