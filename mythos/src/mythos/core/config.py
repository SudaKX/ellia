from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _default_database_url() -> str:
    database_path = PROJECT_ROOT / "data" / "mythos.sqlite3"
    return f"sqlite+aiosqlite:///{database_path.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="MYTHOS_",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = _default_database_url()
    jwt_signing_key: SecretStr | None = None
    refresh_token_pepper: SecretStr | None = None
    jwt_issuer: str = "ellia-mythos"
    jwt_audience: str = "ellia-console"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    refresh_cookie_name: str = "mythos_refresh"
    refresh_cookie_secure: bool | None = None
    request_cache_ttl_seconds: int = 30
    request_cache_maxsize: int = 1_000

    @model_validator(mode="after")
    def configure_auth_secrets(self) -> Settings:
        if self.environment == "production":
            if self.jwt_signing_key is None or self.refresh_token_pepper is None:
                raise ValueError("Production requires JWT and refresh token secrets.")
        else:
            if self.jwt_signing_key is None:
                self.jwt_signing_key = SecretStr(secrets.token_urlsafe(48))
            if self.refresh_token_pepper is None:
                self.refresh_token_pepper = SecretStr(secrets.token_urlsafe(48))
        if len(self.jwt_secret.encode()) < 32:
            raise ValueError("JWT signing key must be at least 32 bytes.")
        if len(self.refresh_pepper.encode()) < 32:
            raise ValueError("Refresh token pepper must be at least 32 bytes.")
        if self.request_cache_ttl_seconds < 1:
            raise ValueError("Request cache TTL must be at least one second.")
        if self.request_cache_maxsize < 1:
            raise ValueError("Request cache size must be at least one entry.")
        return self

    @property
    def cookie_secure(self) -> bool:
        if self.refresh_cookie_secure is not None:
            return self.refresh_cookie_secure
        return self.environment == "production"

    @property
    def jwt_secret(self) -> str:
        assert self.jwt_signing_key is not None
        return self.jwt_signing_key.get_secret_value()

    @property
    def refresh_pepper(self) -> str:
        assert self.refresh_token_pepper is not None
        return self.refresh_token_pepper.get_secret_value()


@lru_cache
def get_settings() -> Settings:
    return Settings()
