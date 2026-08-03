from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import CommandRejected, RequestInProgressError, RequestReplayForbiddenError, ResponseSpec
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.runtime import ApplicationRuntime
from mythos.players.context import RequestContext
from mythos.players.dependencies import get_context
from mythos.players.factory import PlayerNotFoundError
from mythos.players.interface_selection import PlayerInterfaces
from mythos.services.progress.service import CheckpointIncompatibleError, CheckpointNotFoundError

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("")
async def get_progress(
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.PROGRESS))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, object]:
    return runtime.services.progress.snapshot(context.player).body()


@router.post("/checkpoints/restore")
async def restore_checkpoint(
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        result = await runtime.command_executor.execute(
            session,
            identity,
            request_id,
            lambda context: _restore_response(runtime, context),
        )
    except RequestInProgressError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request is in progress.") from error
    except RequestReplayForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request-ID belongs to another player.") from error
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error
    except CheckpointNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Checkpoint not found.") from error
    except CheckpointIncompatibleError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except CommandRejected as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    return JSONResponse(status_code=result.response.status_code, content=result.response.body)


async def _restore_response(runtime: ApplicationRuntime, context) -> ResponseSpec:
    snapshot = await runtime.services.progress.restore(context)
    return ResponseSpec(status_code=200, body={"progress": snapshot.body()}, headers={})
