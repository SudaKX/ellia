from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.commands import (
    CachedResponse,
    RequestInProgressError,
    RequestReplayForbiddenError,
    ResponseFormatError,
    ResponseSpec,
)
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.exceptions import ValidationRejected
from mythos.core.problems import ApiProblem, ProblemType
from mythos.core.runtime import ApplicationRuntime
from mythos.players.loader import PlayerNotFoundError
from mythos.players.interfaces import ProgressTransitionError
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
        result = await runtime.endpoint_executor.execute(
            session,
            identity,
            request_id,
             lambda context: _submit_response(runtime, context, attempt, payload),
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
    except ValidationRejected as error:
        raise ApiProblem(
            ProblemType.VALIDATION_REJECTED,
            status=status.HTTP_409_CONFLICT,
            title="Validation rejected",
            detail=error.reason,
            extensions={"details": error.details} if error.details else {},
        ) from error
    except ProgressTransitionError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except ResponseFormatError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Validation handler failed.") from error
    return _command_response(result)


async def _submit_response(runtime, context, attempt, payload) -> ResponseSpec:
    outcome = await runtime.services.validations.submit(
        context.player,
        attempt,
        payload,
        scope=context.scope,
    )
    return ResponseSpec(status_code=200, body={"accepted": outcome.accepted}, headers={})
