from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import (
    CachedResponse,
    CommandRejected,
    RequestInProgressError,
    RequestReplayForbiddenError,
    ResponseFormatError,
)
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.followups import FollowupFormatError
from mythos.core.runtime import ApplicationRuntime
from mythos.players.factory import PlayerNotFoundError
from mythos.registry.validations import ValidationAttemptNotFoundError

router = APIRouter(prefix="/validations", tags=["validations"])


def _command_response(result: CachedResponse) -> JSONResponse:
    return JSONResponse(
        status_code=result.response.status_code,
        content=result.response.body,
        headers=result.response.headers,
    )


@router.post("/{validation_id}/attempts")
async def submit_attempt(
    validation_id: str,
    payload: dict[str, Any],
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        attempt = runtime.services.validations.attempt(validation_id)
    except ValidationAttemptNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Validation not found.") from error
    try:
        result = await runtime.command_executor.execute(
            session,
            identity,
            request_id,
            lambda context: runtime.services.validations.submit(context, attempt, payload),
        )
    except RequestInProgressError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A request with this Request-ID is still in progress.",
            headers={"Retry-After": "1"},
        ) from error
    except RequestReplayForbiddenError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Request-ID belongs to another player.") from error
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error
    except CommandRejected as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except (FollowupFormatError, ResponseFormatError) as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Validation handler failed.") from error
    return _command_response(result)
