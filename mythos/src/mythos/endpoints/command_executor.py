from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.endpoints.actions import Action, ActionExecutionError
from mythos.endpoints.cache import RequestCache
from mythos.endpoints.execution import ActionRuntime, ResponseBodyBuilder, execute_actions
from mythos.endpoints.models import ActionExecutionResult
from mythos.players.context import PlayerRequestContext
from mythos.players.factory import PlayerFactory


class ActionTransactionExecutor:
    def __init__(self, player_factory: PlayerFactory, request_cache: RequestCache) -> None:
        self._player_factory = player_factory
        self._request_cache = request_cache

    async def execute(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        handler: Callable[[PlayerRequestContext], Awaitable[tuple[Action, ...]]],
    ) -> ActionExecutionResult:
        cached_result = self._request_cache.reserve(request_id, identity.player_id)
        if cached_result is not None:
            return cached_result

        try:
            async with session.begin():
                context = PlayerRequestContext(
                    identity=identity,
                    player=await self._player_factory.load(session, identity.player_id, writable=True),
                    request_id=request_id,
                )
                actions = await handler(context)
                self._require_action_tuple(actions)
                result = await execute_actions(
                    actions,
                    ActionRuntime(
                        context=context,
                        response_builder=ResponseBodyBuilder(),
                    ),
                )
        except BaseException:
            self._request_cache.release(request_id)
            raise

        self._request_cache.complete(request_id, result)
        return result

    @staticmethod
    def _require_action_tuple(actions: object) -> None:
        if not isinstance(actions, tuple):
            raise ActionExecutionError("Handlers must return a tuple of framework Action instances.")
