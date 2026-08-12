from __future__ import annotations

from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from mythos.auth.tokens import PlayerIdentity, decode_access_token
from mythos.core.config import Settings
from mythos.core.dependencies import get_settings_from_request
from mythos.core.problems import ApiProblem, ProblemType

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_player(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings_from_request)],
) -> PlayerIdentity:
    if credentials is None:
        raise ApiProblem(
            ProblemType.ACCESS_TOKEN_MISSING,
            status=status.HTTP_401_UNAUTHORIZED,
            title="Access token required",
            detail="An access token is required for this request.",
        )
    try:
        return decode_access_token(credentials.credentials, settings)
    except ValueError as error:
        raise ApiProblem(
            ProblemType.ACCESS_TOKEN_INVALID,
            status=status.HTTP_401_UNAUTHORIZED,
            title="Invalid access token",
            detail="The access token is invalid or expired.",
        ) from error
