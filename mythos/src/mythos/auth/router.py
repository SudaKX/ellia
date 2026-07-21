from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.dependencies import (
    get_current_player,
    get_session,
    get_settings_from_request,
)
from mythos.auth.schemas import AccessTokenResponse, CredentialsRequest
from mythos.auth.service import (
    AuthService,
    InvalidCredentialsError,
    InvalidRefreshCredentialError,
    UsernameAlreadyExistsError,
)
from mythos.auth.tokens import PlayerContext, RefreshCredential
from mythos.core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_refresh_cookie(
    response: Response,
    credential: RefreshCredential,
    settings: Settings,
) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=credential.cookie_value,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"


def _delete_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api/v1/auth",
    )
    response.headers["Cache-Control"] = "no-store"


def _token_response(access_token: str, settings: Settings) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=access_token,
        expires_in=settings.access_token_ttl_seconds,
    )


def _auth_service(session: AsyncSession, settings: Settings) -> AuthService:
    return AuthService(session, settings)


@router.post("/register", response_model=AccessTokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    credentials: CredentialsRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_request)],
) -> AccessTokenResponse:
    try:
        result = await _auth_service(session, settings).register(
            credentials.username,
            credentials.password,
        )
    except UsernameAlreadyExistsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already exists.") from error

    _set_refresh_cookie(response, result.refresh_credential, settings)
    return _token_response(result.access_token, settings)


@router.post("/login", response_model=AccessTokenResponse)
async def login(
    credentials: CredentialsRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_request)],
) -> AccessTokenResponse:
    try:
        result = await _auth_service(session, settings).login(
            credentials.username,
            credentials.password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password.") from error

    _set_refresh_cookie(response, result.refresh_credential, settings)
    return _token_response(result.access_token, settings)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_request)],
) -> AccessTokenResponse:
    try:
        result = await _auth_service(session, settings).refresh(
            request.cookies.get(settings.refresh_cookie_name)
        )
    except InvalidRefreshCredentialError as error:
        error_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid refresh credential."},
        )
        _delete_refresh_cookie(error_response, settings)
        return error_response

    _set_refresh_cookie(response, result.refresh_credential, settings)
    return _token_response(result.access_token, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    player: Annotated[PlayerContext, Depends(get_current_player)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings_from_request)],
) -> Response:
    await _auth_service(session, settings).logout(player.player_id)
    _delete_refresh_cookie(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
