import asyncio

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from mythos.core.config import Settings
from mythos.core.problems import ProblemType
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.registry.bundle import RegistryBundle


def test_production_rejects_short_auth_secrets() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="production",
            jwt_signing_key=SecretStr("too-short"),
            refresh_token_pepper=SecretStr("also-too-short"),
            file_id_signing_key=SecretStr("file-id-signing-key-with-at-least-32-bytes"),
        )


def test_production_requires_problem_type_base_url() -> None:
    secret = SecretStr("test-secret-with-at-least-32-bytes")
    with pytest.raises(ValidationError, match="MYTHOS_PROBLEM_TYPE_BASE_URL"):
        Settings(
            environment="production",
            jwt_signing_key=secret,
            refresh_token_pepper=secret,
            file_id_signing_key=secret,
        )

    settings = Settings(
        environment="production",
        jwt_signing_key=secret,
        refresh_token_pepper=secret,
        file_id_signing_key=secret,
        problem_type_base_url="https://api.example/problems",
        _env_file=None,
    )
    assert settings.problem_type_url("access-token-invalid") == "https://api.example/problems/access-token-invalid"


def test_object_store_tls_setting_must_match_endpoint_scheme() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            object_store_endpoint="http://127.0.0.1:9000",
            object_store_bucket="mythos",
            object_store_access_key=SecretStr("test-object-store-access-key"),
            object_store_secret_key=SecretStr("test-object-store-secret-key"),
            object_store_use_tls=True,
        )


def test_object_store_endpoint_rejects_path_prefix() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            object_store_endpoint="https://objects.example/api",
            object_store_bucket="mythos",
            object_store_access_key=SecretStr("test-object-store-access-key"),
            object_store_secret_key=SecretStr("test-object-store-secret-key"),
        )


def test_content_cache_lifetime_must_be_shorter_than_content_url_ttl() -> None:
    with pytest.raises(ValidationError):
        Settings(
            environment="test",
            file_content_url_ttl_seconds=60,
            file_content_cache_max_age_seconds=60,
        )


def test_authentication_lifecycle(tmp_path) -> None:
    async def scenario() -> None:
        database_path = tmp_path / "auth.sqlite3"
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{database_path.as_posix()}",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )
        app = create_app(settings, registries=RegistryBundle())

        async with app.router.lifespan_context(app):
            async with app.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

            runtime = app.state.runtime
            assert not hasattr(runtime, "task_service")
            assert runtime.services.tasks is runtime.endpoint_executor._task_service
            assert runtime.services.tasks is runtime.task_command_executor._task_service

            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {"username": "SudaKX", "password": "correct-horse-battery"}

                register_response = await client.post("/api/v1/auth/register", json=payload)
                assert register_response.status_code == 201
                first_access_token = register_response.json()["access_token"]
                first_refresh_cookie = client.cookies[settings.refresh_cookie_name]
                assert register_response.headers["cache-control"] == "no-store"

                duplicate_response = await client.post("/api/v1/auth/register", json=payload)
                assert duplicate_response.status_code == 409
                assert duplicate_response.json()["type"] == settings.problem_type_url(ProblemType.USERNAME_ALREADY_EXISTS)

                invalid_login_response = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "SudaKX", "password": "wrong-password"},
                )
                assert invalid_login_response.status_code == 401
                assert invalid_login_response.headers["content-type"].startswith("application/problem+json")
                assert invalid_login_response.headers.get("www-authenticate") is None
                assert invalid_login_response.headers["cache-control"] == "no-store"
                assert invalid_login_response.json()["type"] == settings.problem_type_url(
                    ProblemType.PRIMARY_CREDENTIALS_INVALID
                )

                refresh_response = await client.post("/api/v1/auth/refresh")
                assert refresh_response.status_code == 200
                refreshed_access_token = refresh_response.json()["access_token"]
                refreshed_cookie = client.cookies[settings.refresh_cookie_name]
                assert refreshed_access_token != first_access_token
                assert refreshed_cookie != first_refresh_cookie

                async with httpx.AsyncClient(
                    transport=transport,
                    base_url="http://test",
                    cookies={settings.refresh_cookie_name: first_refresh_cookie},
                ) as replay_client:
                    replay_response = await replay_client.post("/api/v1/auth/refresh")
                assert replay_response.status_code == 401
                assert replay_response.json()["type"] == settings.problem_type_url(
                    ProblemType.REFRESH_CREDENTIAL_INVALID
                )

                logout_response = await client.post(
                    "/api/v1/auth/logout",
                    headers={"Authorization": f"Bearer {refreshed_access_token}"},
                )
                assert logout_response.status_code == 204

                logged_out_refresh_response = await client.post("/api/v1/auth/refresh")
                assert logged_out_refresh_response.status_code == 401
                assert logged_out_refresh_response.json()["type"] == settings.problem_type_url(
                    ProblemType.REFRESH_CREDENTIAL_INVALID
                )

    asyncio.run(scenario())
