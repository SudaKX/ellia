from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from mythos.core.dependencies import get_runtime
from mythos.core.runtime import ApplicationRuntime
from mythos.players.context import RequestContext
from mythos.players.dependencies import PlayerInterfaces, get_context

router = APIRouter(prefix="/scripts", tags=["scripts"])


@router.get("")
async def list_scripts(
    context: Annotated[
        RequestContext,
        Depends(get_context(PlayerInterfaces.PROGRESS | PlayerInterfaces.ACCOUNTS)),
    ],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, object]:
    return {"items": runtime.services.scripts.visible(context.player)}
