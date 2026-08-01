from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError

from mythos.core.config import Settings
from mythos.persistence.base import utcnow


@dataclass(frozen=True)
class RefreshCredential:
    selector: str
    secret: str

    @property
    def cookie_value(self) -> str:
        return f"{self.selector}.{self.secret}"


@dataclass(frozen=True)
class PlayerIdentity:
    player_id: UUID


def create_refresh_credential() -> RefreshCredential:
    return RefreshCredential(
        selector=secrets.token_urlsafe(16),
        secret=secrets.token_urlsafe(32),
    )


def hash_refresh_secret(secret: str, settings: Settings) -> str:
    return hmac.new(
        settings.refresh_pepper.encode(),
        secret.encode(),
        hashlib.sha256,
    ).hexdigest()


def parse_refresh_credential(value: str | None) -> RefreshCredential | None:
    if value is None:
        return None
    selector, separator, secret = value.partition(".")
    if not separator or not selector or not secret or "." in secret:
        return None
    return RefreshCredential(selector=selector, secret=secret)


def issue_access_token(player_id: UUID, settings: Settings) -> str:
    now = utcnow()
    payload = {
        "sub": str(player_id),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(seconds=settings.access_token_ttl_seconds),
        "jti": str(uuid4()),
        "typ": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> PlayerIdentity:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["sub", "iss", "aud", "iat", "nbf", "exp", "jti", "typ"]},
        )
        if payload["typ"] != "access":
            raise InvalidTokenError("Unexpected token type.")
        return PlayerIdentity(player_id=UUID(payload["sub"]))
    except (InvalidTokenError, KeyError, ValueError) as error:
        raise ValueError("Invalid or expired access token.") from error
