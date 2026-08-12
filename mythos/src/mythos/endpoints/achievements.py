from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.commands import RequestInProgressError, RequestReplayForbiddenError
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.problems import ApiProblem, ProblemType
from mythos.core.runtime import ApplicationRuntime
from mythos.players.dependencies import get_context
from mythos.players.context import RequestContext
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.loader import PlayerNotFoundError
from mythos.services.achievements import AchievementDeletedError, AchievementNotAvailableError


router = APIRouter(prefix="/achievement", tags=["achievement"])


@router.get("")
async def list_achievements(
    context: Annotated[RequestContext, Depends(get_context(PlayerInterfaces.ACHIEVEMENTS))],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
    response: Response,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Vary"] = "Authorization"
    return {"items": [item.body() for item in runtime.services.achievements.snapshots(context.player)]}


@router.post("/check")
async def check_achievements(
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        result = await runtime.achievement_command_executor.check(session, identity, request_id)
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


@router.post("/claim/{public_id}")
async def claim_achievement(
    public_id: str,
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        result = await runtime.achievement_command_executor.claim(session, identity, request_id, public_id)
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
    except AchievementDeletedError as error:
        raise _problem(
            ProblemType.ACHIEVEMENT_DELETED,
            409,
            "Achievement deleted",
            "Deleted achievements cannot be claimed.",
        ) from error
    except AchievementNotAvailableError as error:
        raise _problem(
            ProblemType.ACHIEVEMENT_NOT_AVAILABLE,
            409,
            "Achievement unavailable",
            "The requested achievement is not available for claiming.",
        ) from error
    return JSONResponse(
        status_code=result.response.status_code,
        content=result.response.body,
        headers=result.response.headers,
    )


def _problem(problem_type: ProblemType, problem_status: int, title: str, detail: str) -> ApiProblem:
    return ApiProblem(problem_type, status=problem_status, title=title, detail=detail)
