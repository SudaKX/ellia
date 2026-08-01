from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands.cache import RequestCache
from mythos.core.commands.models import CachedResponse, ResponseSpec
from mythos.players.context import CommandContext
from mythos.players.factory import PlayerFactory

CommandPreCommitHook: TypeAlias = Callable[[AsyncSession, CommandContext], Awaitable[None]]


class CommandTransactionExecutor:
    def __init__(
        self,
        player_factory: PlayerFactory,
        request_cache: RequestCache,
        pre_commit_hooks: tuple[CommandPreCommitHook, ...] = (),
    ) -> None:
        self._player_factory = player_factory
        self._request_cache = request_cache
        self._pre_commit_hooks = pre_commit_hooks

    async def execute(
        self,
        session: AsyncSession,
        identity: PlayerIdentity,
        request_id: UUID,
        operation: Callable[[CommandContext], Awaitable[ResponseSpec]],
    ) -> CachedResponse:
        cached_response = self._request_cache.reserve(request_id, identity.player_id)
        if cached_response is not None:
            return cached_response

        try:
            async with session.begin():
                player = await self._player_factory.create(
                    session, identity.player_id, writable=True
                )
                await player.load_progress()
                await player.load_artifacts()
                context = CommandContext(
                    identity=identity,
                    player=player,
                    request_id=request_id,
                )
                response = await operation(context)
                for hook in self._pre_commit_hooks:
                    await hook(session, context)
                completed = CachedResponse(
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
        except BaseException:
            self._request_cache.release(request_id)
            raise

        self._request_cache.complete(request_id, completed)
        return completed
