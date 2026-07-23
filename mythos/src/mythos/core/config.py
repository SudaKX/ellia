from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

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
    file_id_signing_key: SecretStr | None = None
    jwt_issuer: str = "ellia-mythos"
    jwt_audience: str = "ellia-console"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000
    refresh_cookie_name: str = "mythos_refresh"
    refresh_cookie_secure: bool | None = None
    request_cache_ttl_seconds: int = 30
    request_cache_maxsize: int = 1_000
    object_store_endpoint: str | None = None
    object_store_region: str = "us-east-1"
    object_store_bucket: str | None = None
    object_store_access_key: SecretStr | None = None
    object_store_secret_key: SecretStr | None = None
    object_store_use_tls: bool = True
    file_download_url_ttl_seconds: int = 60

    @model_validator(mode="after")
    def configure_secrets(self) -> Settings:
        if self.environment == "production":
            if (
                self.jwt_signing_key is None
                or self.refresh_token_pepper is None
                or self.file_id_signing_key is None
            ):
                raise ValueError("Production requires JWT, refresh, and file ID secrets.")
        else:
            if self.jwt_signing_key is None:
                self.jwt_signing_key = SecretStr(secrets.token_urlsafe(48))
            if self.refresh_token_pepper is None:
                self.refresh_token_pepper = SecretStr(secrets.token_urlsafe(48))
            if self.file_id_signing_key is None:
                self.file_id_signing_key = SecretStr(secrets.token_urlsafe(48))
        if len(self.jwt_secret.encode()) < 32:
            raise ValueError("JWT signing key must be at least 32 bytes.")
        if len(self.refresh_pepper.encode()) < 32:
            raise ValueError("Refresh token pepper must be at least 32 bytes.")
        if len(self.file_id_secret.encode()) < 32:
            raise ValueError("File ID signing key must be at least 32 bytes.")
        if self.request_cache_ttl_seconds < 1:
            raise ValueError("Request cache TTL must be at least one second.")
        if self.request_cache_maxsize < 1:
            raise ValueError("Request cache size must be at least one entry.")
        if not 1 <= self.file_download_url_ttl_seconds <= 300:
            raise ValueError("File download URL TTL must be between one and 300 seconds.")
        object_store_values = (
            self.object_store_endpoint,
            self.object_store_bucket,
            self.object_store_access_key,
            self.object_store_secret_key,
        )
        if any(value is not None for value in object_store_values) and not all(object_store_values):
            raise ValueError("Object store configuration must provide endpoint, bucket, access key, and secret key.")
        if self.object_store_configured:
            assert self.object_store_endpoint is not None
            endpoint = urlparse(self.object_store_endpoint)
            if endpoint.scheme not in {"http", "https"} or not endpoint.netloc:
                raise ValueError("Object store endpoint must be an absolute HTTP URL.")
            if endpoint.path not in {"", "/"} or endpoint.params or endpoint.query or endpoint.fragment:
                raise ValueError("Object store endpoint cannot include a path, query, or fragment.")
            if self.object_store_use_tls != (endpoint.scheme == "https"):
                raise ValueError("Object store TLS setting must match the endpoint scheme.")
            if self.environment == "production" and endpoint.scheme != "https":
                raise ValueError("Production object storage requires an HTTPS endpoint.")
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

    @property
    def file_id_secret(self) -> str:
        assert self.file_id_signing_key is not None
        return self.file_id_signing_key.get_secret_value()

    @property
    def object_store_configured(self) -> bool:
        return self.object_store_endpoint is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
