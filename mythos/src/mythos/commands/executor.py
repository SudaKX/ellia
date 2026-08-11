from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.commands.cache import RequestCache
from mythos.commands.models import CachedResponse, ResponseSpec
from mythos.commands.pipeline import PipelinedTransaction
from mythos.core.followups import ContextScope
from mythos.players.context import CommandContext
from mythos.players.loader import PlayerLoader, PlayerNotFoundError
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.services.tasks.service import TaskHandlerFailure, TaskRunReport, TaskService
from mythos.services.achievements.service import (
    AchievementDeletedError,
    AchievementNotAvailableError,
    AchievementCheckResult,
    AchievementService,
)


_logger = logging.getLogger(__name__)


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
        achievement_service: AchievementService | None = None,
    ) -> None:
        self._player_loader = player_loader
        self._request_cache = request_cache
        self._task_service = task_service
        self._achievement_service = achievement_service
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
            completed = await self._run_achievement_after_operation(
                session,
                identity.player_id,
                completed,
            )
            lease.complete(completed)
            return completed

    async def _run_achievement_after_operation(
        self,
        session: AsyncSession,
        player_id: UUID,
        completed: CachedResponse,
    ) -> CachedResponse:
        if self._achievement_service is None:
            return completed
        warnings: list[dict[str, str]] = []
        check_result: AchievementCheckResult | None = None
        try:
            async with session.begin():
                player = await self._load_achievement_player(session, player_id)

                async def check_operation(_session: AsyncSession, current_player: Player) -> AchievementCheckResult:
                    return await self._achievement_service.check(current_player)

                check_result = await self._pipeline.run(session, player, check_operation)
        except PlayerNotFoundError:
            raise
        except Exception as error:
            _logger.exception("Achievement check failed for player=%s", player_id, exc_info=error)
            warnings.append(_achievement_warning("check"))
        if check_result is not None and check_result.effect_stable_ids:
            try:
                async with session.begin():
                    player = await self._load_achievement_player(session, player_id)

                    async def effect_operation(_session: AsyncSession, current_player: Player) -> tuple[str, ...]:
                        return await self._achievement_service.apply_effects(
                            current_player,
                            check_result.effect_stable_ids,
                        )

                    await self._pipeline.run(session, player, effect_operation)
            except PlayerNotFoundError:
                raise
            except Exception as error:
                _logger.exception("Achievement effect failed for player=%s", player_id, exc_info=error)
                warnings.append(_achievement_warning("effect"))
        return _with_warnings(completed, warnings)

    async def _load_achievement_player(self, session: AsyncSession, player_id: UUID) -> Player:
        interfaces = (
            self._achievement_service.catalog.dependencies
            | PlayerInterfaces.ACHIEVEMENTS
            | PlayerInterfaces.PROGRESS
        )
        return await self._player_loader.load_writable(session, player_id, interfaces=interfaces)

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


class AchievementCommandExecutor:
    """Run achievement check and claim commands without Task or Operation phases."""

    def __init__(
        self,
        player_loader: PlayerLoader,
        achievement_service: AchievementService,
        request_cache: RequestCache,
        pipelined_transaction: PipelinedTransaction,
    ) -> None:
        self._player_loader = player_loader
        self._achievement_service = achievement_service
        self._request_cache = request_cache
        self._pipeline = pipelined_transaction

    async def check(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
    ) -> CachedResponse:
        with self._request_cache.lease(request_id, identity.player_id) as lease:
            if lease.replay is not None:
                return lease.replay
            warnings: list[dict[str, str]] = []
            result: AchievementCheckResult | None = None
            try:
                async with session.begin():
                    player = await self._load_player(session, identity.player_id)

                    async def check_operation(_session: AsyncSession, current_player: Player) -> AchievementCheckResult:
                        return await self._achievement_service.check(current_player)

                    result = await self._pipeline.run(session, player, check_operation)
            except PlayerNotFoundError:
                raise
            except Exception as error:
                _logger.exception("Achievement check failed for player=%s", identity.player_id, exc_info=error)
                warnings.append(_achievement_warning("check"))
            if result is not None and result.effect_stable_ids:
                try:
                    async with session.begin():
                        player = await self._load_player(session, identity.player_id)

                        async def effect_operation(_session: AsyncSession, current_player: Player) -> tuple[str, ...]:
                            return await self._achievement_service.apply_effects(
                                current_player,
                                result.effect_stable_ids,
                            )

                        await self._pipeline.run(session, player, effect_operation)
                except PlayerNotFoundError:
                    raise
                except Exception as error:
                    _logger.exception("Achievement effect failed for player=%s", identity.player_id, exc_info=error)
                    warnings.append(_achievement_warning("effect"))
            response = self._response(
                identity.player_id,
                {"check": result.body(self._achievement_service.catalog) if result is not None else {}},
                warnings,
            )
            lease.complete(response)
            return response

    async def claim(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        public_id: str,
    ) -> CachedResponse:
        with self._request_cache.lease(request_id, identity.player_id) as lease:
            if lease.replay is not None:
                return lease.replay
            warnings: list[dict[str, str]] = []
            snapshot = None
            try:
                async with session.begin():
                    player = await self._load_player(session, identity.player_id)

                    async def claim_operation(_session: AsyncSession, current_player: Player):
                        return await self._achievement_service.claim(current_player, public_id)

                    snapshot = await self._pipeline.run(session, player, claim_operation)
            except (AchievementDeletedError, AchievementNotAvailableError, PlayerNotFoundError):
                raise
            except Exception as error:
                _logger.exception(
                    "Achievement claim effect failed for player=%s public_id=%s",
                    identity.player_id,
                    public_id,
                    exc_info=error,
                )
                warnings.append(_achievement_warning("effect", public_id=public_id))
            response = self._response(
                identity.player_id,
                {"achievement": snapshot.body() if snapshot is not None else {"public_id": public_id}},
                warnings,
            )
            lease.complete(response)
            return response

    async def _load_player(self, session: AsyncSession, player_id: UUID) -> Player:
        interfaces = (
            self._achievement_service.catalog.dependencies
            | PlayerInterfaces.ACHIEVEMENTS
            | PlayerInterfaces.PROGRESS
        )
        return await self._player_loader.load_writable(session, player_id, interfaces=interfaces)

    @staticmethod
    def _response(
        player_id: UUID,
        content: dict[str, object],
        warnings: list[dict[str, str]],
    ) -> CachedResponse:
        body: dict[str, object] = {"content": content, "followups": []}
        if warnings:
            body["warn"] = warnings
        return CachedResponse(
            owner_player_id=player_id,
            response=ResponseSpec(status_code=200, body=body, headers={}),
        )


def _achievement_warning(stage: str, *, public_id: str | None = None) -> dict[str, str]:
    warning = {
        "code": f"achievement-{stage}-failed",
        "stage": f"achievement.{stage}",
        "message": (
            "Achievement check was not completed."
            if stage == "check"
            else "Achievement reward was not applied. Retry with /achievement/check."
        ),
    }
    if public_id is not None:
        warning["public_id"] = public_id
    return warning


def _with_warnings(completed: CachedResponse, warnings: list[dict[str, str]]) -> CachedResponse:
    if not warnings:
        return completed
    body = dict(completed.response.body)
    body["warn"] = [*body.get("warn", []), *warnings]
    return CachedResponse(
        owner_player_id=completed.owner_player_id,
        response=ResponseSpec(
            status_code=completed.response.status_code,
            body=body,
            headers=completed.response.headers,
        ),
    )
