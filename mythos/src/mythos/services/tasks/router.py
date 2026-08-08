from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import RequestInProgressError, RequestReplayForbiddenError
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.runtime import ApplicationRuntime
from mythos.players.context import RequestContext
from mythos.players.dependencies import get_context
from mythos.players.factory import PlayerNotFoundError
from mythos.players.interface_selection import PlayerInterfaces

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("")
async def list_tasks(
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.TASKS))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    response: Response,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return runtime.services.tasks.snapshot(context.player)


@router.post("/process")
async def process_tasks(
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        result = await runtime.command_executor.execute_tasks(session, identity, request_id)
    except RequestInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request with this Request-ID is still in progress.",
            headers={"Retry-After": "1"},
        ) from error
    except RequestReplayForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request-ID belongs to another player.") from error
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.") from error
    return JSONResponse(
        status_code=result.response.status_code,
        content=result.response.body,
        headers=result.response.headers,
    )
