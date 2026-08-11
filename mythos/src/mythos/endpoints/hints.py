from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.commands import RequestInProgressError, RequestReplayForbiddenError, ResponseSpec
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.problems import ApiProblem, ProblemType
from mythos.core.runtime import ApplicationRuntime
from mythos.players.context import RequestContext
from mythos.players.dependencies import get_context
from mythos.players.loader import PlayerNotFoundError
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.interfaces.credits import InsufficientCreditsError
from mythos.services.hints.service import (
    HintContentVersionMismatchError,
    HintNotFoundError,
    HintUnavailableError,
)
from mythos.services.object_store.service import ObjectStoreError, ObjectStoreUnavailableError


router = APIRouter(prefix="/hints", tags=["hints"])


@router.get("")
async def list_hints(
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    response: Response,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return {"hints": [hint.body() for hint in runtime.services.hints.list(context.player)]}


@router.post("/{hint_id}/disclose")
async def disclose_hint(
    hint_id: str,
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        result = await runtime.endpoint_executor.execute(
            session,
            identity,
            request_id,
             lambda context: _disclose_response(runtime.services.hints, context.player, hint_id),
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found.") from error
    except HintNotFoundError as error:
        raise _problem(ProblemType.HINT_NOT_FOUND, 404, "Hint not found", "The requested hint does not exist.") from error
    except HintUnavailableError as error:
        raise _problem(ProblemType.HINT_UNAVAILABLE, 409, "Hint unavailable", "The requested hint is not available.") from error
    except InsufficientCreditsError as error:
        raise _problem(ProblemType.INSUFFICIENT_CREDITS, 409, "Insufficient credits", "There are not enough VTB to disclose this hint.") from error
    return JSONResponse(
        status_code=result.response.status_code,
        content=result.response.body,
        headers=result.response.headers,
    )


async def _disclose_response(service, player, hint_id: str) -> ResponseSpec:
    summary = await service.disclose(player, hint_id)
    return ResponseSpec(status_code=200, body={"hint": summary.body()}, headers={})


@router.get("/{hint_id}/{content_token}/content-url")
async def issue_content_url(
    hint_id: str,
    content_token: str,
    response: Response,
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ALL))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = runtime.services.hints.content_url_cache_control
    response.headers["Vary"] = "Authorization"
    response.headers["ETag"] = f'"{content_token}"'
    try:
        issued = await runtime.services.hints.issue_content_url(context.player, hint_id, content_token)
    except HintNotFoundError as error:
        raise _problem(ProblemType.HINT_NOT_FOUND, 404, "Hint not found", "The requested hint does not exist.") from error
    except HintUnavailableError as error:
        raise _problem(ProblemType.HINT_UNAVAILABLE, 403, "Hint unavailable", "The requested hint is not available.") from error
    except HintContentVersionMismatchError as error:
        raise _problem(
            ProblemType.HINT_CONTENT_VERSION_MISMATCH,
            412,
            "Hint content is stale",
            "Refresh the hint metadata before requesting a new content URL.",
        ) from error
    except ObjectStoreUnavailableError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Object storage is unavailable.") from error
    except ObjectStoreError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to issue hint URL.") from error
    return {
        "url": issued.url,
        "expires_at": issued.expires_at.isoformat(),
        "content_token": content_token,
    }


def _problem(problem_type: ProblemType, problem_status: int, title: str, detail: str) -> ApiProblem:
    return ApiProblem(problem_type, status=problem_status, title=title, detail=detail)
