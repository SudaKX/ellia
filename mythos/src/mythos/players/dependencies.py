from __future__ import annotations

from collections.abc import Awaitable, Callable
from enum import IntFlag
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.runtime import ApplicationRuntime
from mythos.players.context import RequestContext
from mythos.players.factory import PlayerNotFoundError


class PlayerInterfaces(IntFlag):
    NONE = 0
    PROGRESS = 1
    ARTIFACTS = 2
    ACCOUNTS = 4
    ALL = PROGRESS | ARTIFACTS | ACCOUNTS


def get_context(
    interfaces: PlayerInterfaces,
) -> Callable[..., Awaitable[RequestContext]]:
    async def _resolve_context(
        identity: Annotated[PlayerIdentity, Depends(get_current_player)],
        session: Annotated[AsyncSession, Depends(get_session)],
        runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    ) -> RequestContext:
        try:
            player = await runtime.player_factory.create(
                session, identity.player_id, writable=False
            )
        except PlayerNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Player progress not found.",
            ) from error

        if PlayerInterfaces.PROGRESS in interfaces:
            await player.load_progress()
        if PlayerInterfaces.ARTIFACTS in interfaces:
            await player.load_artifacts()
        if PlayerInterfaces.ACCOUNTS in interfaces:
            await player.load_accounts()

        return RequestContext(identity=identity, player=player)

    return _resolve_context
