from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import get_current_player
from mythos.auth.tokens import PlayerIdentity
from mythos.core.commands import RequestInProgressError, RequestReplayForbiddenError, ResponseSpec
from mythos.core.dependencies import get_runtime, get_session
from mythos.core.runtime import ApplicationRuntime
from mythos.core.problems import ApiProblem, ProblemType, validation_errors
from mythos.players.context import CommandContext
from mythos.players.factory import PlayerNotFoundError
from mythos.services.accounts.schemas import AccountLoginRequest
from mythos.services.accounts.service import AccountService, InvalidAccountCredentialsError

router = APIRouter(prefix="/vac", tags=["virtual-accounts"])
_AccountOperation = Callable[[CommandContext], Awaitable[ResponseSpec]]


@router.post("/login")
async def login(
    request: Request,
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    try:
        payload = AccountLoginRequest.model_validate(await request.json())
    except json.JSONDecodeError as error:
        raise ApiProblem(
            ProblemType.INVALID_REQUEST,
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Invalid request",
            detail="One or more request values are invalid.",
            extensions={"errors": [{"pointer": "/", "reason": "Request body must be valid JSON."}]},
        ) from error
    except ValidationError as error:
        raise ApiProblem(
            ProblemType.INVALID_REQUEST,
            status=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Invalid request",
            detail="One or more request values are invalid.",
            extensions={"errors": validation_errors(error.errors())},
        ) from error
    return await _execute(
        runtime,
        session,
        identity,
        request_id,
        lambda context: _login_response(runtime.services.accounts, context, payload),
    )


@router.post("/logout")
async def logout(
    request_id: Annotated[UUID, Header(alias="Request-ID")],
    identity: Annotated[PlayerIdentity, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    runtime: Annotated[ApplicationRuntime, Depends(get_runtime)],
) -> JSONResponse:
    return await _execute(
        runtime,
        session,
        identity,
        request_id,
        lambda context: _logout_response(runtime.services.accounts, context),
    )


async def _execute(
    runtime: ApplicationRuntime,
    session: AsyncSession,
    identity: PlayerIdentity,
    request_id: UUID,
    operation: _AccountOperation,
) -> JSONResponse:
    try:
        result = await runtime.command_executor.execute(session, identity, request_id, operation)
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
    except InvalidAccountCredentialsError as error:
        raise ApiProblem(
            ProblemType.VIRTUAL_ACCOUNT_INVALID_CREDENTIALS,
            status=status.HTTP_401_UNAUTHORIZED,
            title="Invalid virtual account credentials",
            detail="The supplied virtual account credentials are invalid.",
        ) from error
    return JSONResponse(status_code=result.response.status_code, content=result.response.body)


async def _login_response(
    service: AccountService,
    context: CommandContext,
    payload: AccountLoginRequest,
) -> ResponseSpec:
    snapshot = await service.login(context, payload.username, payload.password)
    return ResponseSpec(status_code=status.HTTP_200_OK, body=snapshot.body(), headers={})


async def _logout_response(service: AccountService, context: CommandContext) -> ResponseSpec:
    snapshot = await service.logout(context)
    return ResponseSpec(status_code=status.HTTP_200_OK, body=snapshot.body(), headers={})
