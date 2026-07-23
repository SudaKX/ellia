from __future__ import annotations

from typing import Any, Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.endpoints.actions import (
    Action,
    ActionExecutionError,
    EffectAction,
    FollowupAction,
    RejectAction,
    ResponseAction,
)
from mythos.endpoints.cache import RequestCache
from mythos.endpoints.execution import ActionRuntime, ResponseBodyBuilder, execute_actions
from mythos.endpoints.models import ActionExecutionResult
from mythos.players.context import PlayerRequestContext
from mythos.players.factory import PlayerFactory
from mythos.registry.modules import ModuleCatalog


class EndpointDispatcher:
    def __init__(self, catalog: ModuleCatalog, request_cache: RequestCache) -> None:
        self._catalog = catalog
        self._request_cache = request_cache

    async def dispatch_view(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        endpoint_id: str,
    ) -> dict[str, Any]:
        registrations = self._catalog.view_callbacks(endpoint_id)
        context = PlayerRequestContext(
            identity=identity,
            player=await PlayerFactory.load(session, identity.player_id, writable=False),
        )
        items: list[dict[str, Any]] = []
        followups: list[dict[str, Any]] = []

        for registration in registrations:
            actions = await registration.callback(context)
            self._require_action_tuple(actions)
            self._validate_view_actions(actions)
            result = await execute_actions(
                actions,
                ActionRuntime(
                    context=context,
                    response_builder=ResponseBodyBuilder(),
                ),
            )
            if result.status_code != 200 or result.headers:
                raise ActionExecutionError("View callbacks may only produce an unadorned 200 response.")
            items.append({"stable_id": registration.stable_id, "data": result.body})
            followups.extend(result.followups)

        return {"items": items, "followups": followups}

    async def dispatch_command(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        endpoint_id: str,
        stable_id: str,
        payload: Mapping[str, Any],
        request_id: UUID,
    ) -> ActionExecutionResult:
        registration = self._catalog.command_callback(endpoint_id, stable_id)
        cached_result = self._request_cache.reserve(request_id, identity.player_id)
        if cached_result is not None:
            return cached_result

        try:
            async with session.begin():
                context = PlayerRequestContext(
                    identity=identity,
                    player=await PlayerFactory.load(session, identity.player_id, writable=True),
                    request_id=request_id,
                )
                actions = await registration.callback(context, payload)
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
            raise ActionExecutionError("Callbacks must return a tuple of framework Action instances.")

    @staticmethod
    def _validate_view_actions(actions: tuple[Action, ...]) -> None:
        for action in actions:
            if not isinstance(action, (ResponseAction, FollowupAction)):
                if isinstance(action, (EffectAction, RejectAction)):
                    raise ActionExecutionError("View callbacks cannot return effects or rejection actions.")
                raise ActionExecutionError("View callbacks may only return response and followup actions.")
