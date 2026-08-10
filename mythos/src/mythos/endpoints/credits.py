from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Response

from mythos.players.context import RequestContext
from mythos.players.dependencies import get_context
from mythos.players.interfaces import PlayerInterfaces


router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("")
async def get_credits(
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.CREDITS))],
    response: Response,
) -> dict[str, int]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return {"vtb": context.player.credits.vtb, "version": context.player.credits.version}
