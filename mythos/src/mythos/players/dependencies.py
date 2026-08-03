from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.runtime import ApplicationRuntime
from mythos.players.context import RequestContext
from mythos.players.factory import PlayerNotFoundError
from mythos.players.interface_selection import PlayerInterfaces


def get_context(
    interfaces: PlayerInterfaces = PlayerInterfaces.ALL,
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

        await player.load_interfaces(interfaces)

        return RequestContext(identity=identity, player=player)

    return _resolve_context
