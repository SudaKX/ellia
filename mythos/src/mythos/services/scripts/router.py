from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.dependencies import get_session
from mythos.core.runtime import ApplicationRuntime
from mythos.players.factory import PlayerNotFoundError

router = APIRouter(prefix="/scripts", tags=["scripts"])


def _runtime(request: Request) -> ApplicationRuntime:
    return request.app.state.runtime


@router.get("")
async def list_scripts(
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(_runtime)],
) -> dict[str, object]:
    try:
        player = await runtime.player_factory.load(session, identity.player_id, writable=False)
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error
    return {"items": runtime.services.scripts.visible(player)}
