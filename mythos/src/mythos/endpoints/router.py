from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.dependencies import get_session
from mythos.endpoints.actions import ActionExecutionError, ActionRejected
from mythos.endpoints.cache import RequestInProgressError, RequestReplayForbiddenError
from mythos.endpoints.dispatcher import EndpointDispatcher
from mythos.endpoints.models import ActionExecutionResult, CommandRequest
from mythos.players.factory import PlayerNotFoundError
from mythos.registry.errors import CallbackNotFoundError, EndpointNotFoundError

router = APIRouter(tags=["endpoints"])


def _dispatcher_from_request(request: Request) -> EndpointDispatcher:
    return request.app.state.runtime.endpoint_dispatcher


def _command_response(result: ActionExecutionResult) -> JSONResponse:
    return JSONResponse(
        status_code=result.status_code,
        content={"data": result.body, "followups": list(result.followups), "state_revision": result.state_revision},
        headers=result.headers,
    )


@router.get("/views/{endpoint_id}")
async def read_view(
    endpoint_id: str,
    player: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[EndpointDispatcher, Depends(_dispatcher_from_request)],
) -> dict[str, object]:
    try:
        return await dispatcher.dispatch_view(session, player, endpoint_id)
    except EndpointNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="View endpoint not found.") from error
    except PlayerNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player progress not found.") from error
    except ActionExecutionError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="View callback failed.") from error


@router.post("/commands/{endpoint_id}")
async def execute_command(
    endpoint_id: str,
    command: CommandRequest,
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    player: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dispatcher: Annotated[EndpointDispatcher, Depends(_dispatcher_from_request)],
) -> JSONResponse:
    try:
        result = await dispatcher.dispatch_command(
            session,
            player,
            endpoint_id,
            command.stable_id,
            command.payload,
            request_id,
        )
    except EndpointNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command endpoint not found.") from error
    except CallbackNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Command callback not found.") from error
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
    except ActionRejected as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
    except ActionExecutionError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Command callback failed.") from error
    return _command_response(result)
