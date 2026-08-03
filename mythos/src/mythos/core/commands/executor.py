from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeAlias
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

CommandPreCommitHook: TypeAlias = Callable[[AsyncSession, Player], Awaitable[None]]
NoCacheOperation: TypeAlias = Callable[[Player], Awaitable[None]]


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
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
    ) -> CachedResponse:
        cached_response = self._request_cache.reserve(request_id, identity.player_id)
        if cached_response is not None:
            return cached_response

        try:
            async with session.begin():
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

    async def execute_nocache(
        self,
        session: AsyncSession,
        player_id: UUID,
        operation: NoCacheOperation,
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
        run_pre_commit_hooks: bool = True,
    ) -> None:
        async with session.begin():
            await self.execute_nocache_itx(
                session,
                player_id,
                operation,
                interfaces=interfaces,
                run_pre_commit_hooks=run_pre_commit_hooks,
            )

    async def execute_nocache_itx(
        self,
        session: AsyncSession,
        player_id: UUID,
        operation: NoCacheOperation,
        *,
        interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
        run_pre_commit_hooks: bool = True,
    ) -> None:
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
