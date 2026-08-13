from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path.cwd().resolve()
_DEFAULT_PROBLEM_TYPE_BASE_URL = "https://problems.invalid/ellia/problems"


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
    problem_type_base_url: str = _DEFAULT_PROBLEM_TYPE_BASE_URL
    object_store_endpoint: str | None = None
    object_store_region: str = "us-east-1"
    object_store_bucket: str | None = None
    object_store_access_key: SecretStr | None = None
    object_store_secret_key: SecretStr | None = None
    object_store_use_tls: bool = True
    file_content_url_ttl_seconds: int = 43_200
    file_content_cache_max_age_seconds: int = 42_900
    file_download_url_ttl_seconds: int = 900
    puzzle_root: Path = PROJECT_ROOT / "puzzles"
    checkpoint_directory: Path = PROJECT_ROOT / "data" / "checkpoints"
    artifact_template_snapshot_path: Path | None = None
    virtual_account_template_snapshot_path: Path | None = None
    task_registry_snapshot_path: Path | None = None
    credit_template_snapshot_path: Path | None = None
    allow_empty_virtual_account_catalog_reconciliation: bool = False

    @model_validator(mode="after")
    def configure_secrets(self) -> Settings:
        self.database_url = resolve_database_url(self.database_url)
        self.puzzle_root = resolve_runtime_path(self.puzzle_root)
        self.checkpoint_directory = resolve_runtime_path(self.checkpoint_directory)
        if self.artifact_template_snapshot_path is not None:
            self.artifact_template_snapshot_path = resolve_runtime_path(self.artifact_template_snapshot_path)
        if self.virtual_account_template_snapshot_path is not None:
            self.virtual_account_template_snapshot_path = resolve_runtime_path(
                self.virtual_account_template_snapshot_path
            )
        if self.task_registry_snapshot_path is not None:
            self.task_registry_snapshot_path = resolve_runtime_path(self.task_registry_snapshot_path)
        if self.credit_template_snapshot_path is not None:
            self.credit_template_snapshot_path = resolve_runtime_path(self.credit_template_snapshot_path)
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
        problem_type_base = urlparse(self.problem_type_base_url)
        try:
            port = problem_type_base.port
        except ValueError as error:
            raise ValueError("Problem type base URL must use a valid port.") from error
        if (
            problem_type_base.scheme not in {"http", "https"}
            or not problem_type_base.netloc
            or not problem_type_base.hostname
            or problem_type_base.username is not None
            or problem_type_base.password is not None
            or problem_type_base.params
            or problem_type_base.query
            or problem_type_base.fragment
            or "?" in self.problem_type_base_url
            or "#" in self.problem_type_base_url
            or any(character.isspace() for character in self.problem_type_base_url)
        ):
            raise ValueError("Problem type base URL must be an absolute HTTP URL without query or fragment.")
        del port
        if self.environment == "production":
            if self.problem_type_base_url == _DEFAULT_PROBLEM_TYPE_BASE_URL:
                raise ValueError("Production requires MYTHOS_PROBLEM_TYPE_BASE_URL.")
            if problem_type_base.scheme != "https":
                raise ValueError("Production problem type base URL requires HTTPS.")
        if not 1 <= self.file_content_url_ttl_seconds <= 43_200:
            raise ValueError("File content URL TTL must be between one second and 12 hours.")
        if not 0 <= self.file_content_cache_max_age_seconds < self.file_content_url_ttl_seconds:
            raise ValueError("File content cache max-age must be non-negative and shorter than the URL TTL.")
        if not 1 <= self.file_download_url_ttl_seconds <= 43_200:
            raise ValueError("File download URL TTL must be between one second and 12 hours.")
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

    def problem_type_url(self, problem_type: str) -> str:
        return f"{self.problem_type_base_url.rstrip('/')}/{problem_type}"

    @property
    def artifact_snapshot_path(self) -> Path:
        if self.artifact_template_snapshot_path is not None:
            return self.artifact_template_snapshot_path
        database_path = make_database_path(self.database_url)
        if database_path is not None:
            return database_path.parent / "artifact-template-catalog.json"
        return PROJECT_ROOT / "data" / "artifact-template-catalog.json"

    @property
    def virtual_account_snapshot_path(self) -> Path:
        if self.virtual_account_template_snapshot_path is not None:
            return self.virtual_account_template_snapshot_path
        database_path = make_database_path(self.database_url)
        if database_path is not None:
            return database_path.parent / "virtual-account-template-catalog.json"
        return PROJECT_ROOT / "data" / "virtual-account-template-catalog.json"

    @property
    def task_snapshot_path(self) -> Path:
        if self.task_registry_snapshot_path is not None:
            return self.task_registry_snapshot_path
        database_path = make_database_path(self.database_url)
        if database_path is not None:
            return database_path.parent / "task-registry-catalog.json"
        return PROJECT_ROOT / "data" / "task-registry-catalog.json"

    @property
    def credit_snapshot_path(self) -> Path:
        if self.credit_template_snapshot_path is not None:
            return self.credit_template_snapshot_path
        database_path = make_database_path(self.database_url)
        if database_path is not None:
            return database_path.parent / "credit-template-catalog.json"
        return PROJECT_ROOT / "data" / "credit-template-catalog.json"


def make_database_path(database_url: str) -> Path | None:
    url = make_url(database_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or not database or database == ":memory:" or database.startswith("file:"):
        return None
    return resolve_database_file_path(database)


def resolve_runtime_path(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def resolve_database_url(database_url: str) -> str:
    url = make_url(database_url)
    database = url.database
    if url.get_backend_name() != "sqlite" or not database or database == ":memory:" or database.startswith("file:"):
        return database_url
    resolved = resolve_database_file_path(database)
    return url.set(database=resolved.as_posix()).render_as_string(hide_password=False)


def resolve_database_file_path(database: str) -> Path:
    path = Path(database)
    if not path.is_absolute() and not database.startswith(("/", "\\")):
        path = PROJECT_ROOT / path
    return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
