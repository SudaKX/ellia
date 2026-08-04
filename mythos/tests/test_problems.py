import asyncio

import httpx
import pytest
from fastapi import HTTPException

from mythos.core.config import Settings
from mythos.core.problems import ProblemType
from mythos.main import create_app


def test_problem_type_base_url_requires_an_absolute_http_url() -> None:
    with pytest.raises(ValueError, match="Problem type base URL"):
        Settings(problem_type_base_url="/problems")
    with pytest.raises(ValueError, match="Problem type base URL"):
        Settings(problem_type_base_url="https://user:secret@errors.example/problems")
    with pytest.raises(ValueError, match="Problem type base URL"):
        Settings(problem_type_base_url="https://errors.example/problem types")
    with pytest.raises(ValueError, match="Problem type base URL"):
        Settings(problem_type_base_url="https://errors.example/problems?")
    with pytest.raises(ValueError, match="Problem type base URL"):
        Settings(problem_type_base_url="https://errors.example/problems#")

    settings = Settings(problem_type_base_url="https://errors.example/problems/")
    assert settings.problem_type_url(ProblemType.ACCESS_TOKEN_INVALID) == (
        "https://errors.example/problems/access-token-invalid"
    )


def test_http_errors_use_problem_details_without_bearer_challenge() -> None:
    async def scenario() -> None:
        settings = Settings(problem_type_base_url="https://errors.example/problems")
        app = create_app(settings)

        @app.get("/api/v1/explicit-auth-challenge")
        async def explicit_auth_challenge() -> None:
            raise HTTPException(
                status_code=401,
                detail="An upstream authentication challenge was supplied.",
                headers={"WWW-Authenticate": 'Bearer realm="upstream"'},
            )

        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                missing_token = await client.get("/api/v1/files/version")
                missing_route = await client.get("/api/v1/missing")
                invalid_request = await client.post(
                    "/api/v1/auth/login",
                    json={"username": "x", "password": "short"},
                )
                malformed_json = await client.post(
                    "/api/v1/auth/login",
                    content=b'{"username":',
                    headers={"Content-Type": "application/json"},
                )
                invalid_utf8 = await client.post(
                    "/api/v1/auth/login",
                    content=b"\xff",
                    headers={"Content-Type": "application/json"},
                )
                explicit_challenge = await client.get("/api/v1/explicit-auth-challenge")
                openapi = await client.get("/openapi.json")

        assert missing_token.status_code == 401
        assert missing_token.headers["content-type"].startswith("application/problem+json")
        assert missing_token.headers.get("www-authenticate") is None
        assert missing_token.headers["cache-control"] == "no-store"
        assert missing_token.json()["type"] == settings.problem_type_url(ProblemType.ACCESS_TOKEN_MISSING)
        assert missing_token.json()["instance"].startswith("urn:uuid:")

        assert explicit_challenge.status_code == 401
        assert explicit_challenge.headers["www-authenticate"] == 'Bearer realm="upstream"'
        assert explicit_challenge.json()["type"] == "about:blank"

        assert missing_route.status_code == 404
        assert missing_route.headers["content-type"].startswith("application/problem+json")
        assert missing_route.json()["type"] == "about:blank"
        assert missing_route.json()["title"] == "Not Found"

        assert invalid_request.status_code == 422
        assert invalid_request.headers["content-type"].startswith("application/problem+json")
        assert invalid_request.json()["type"] == settings.problem_type_url(ProblemType.INVALID_REQUEST)
        assert invalid_request.json()["errors"]
        assert invalid_request.json()["errors"][0]["pointer"].startswith("/")

        for response in (malformed_json, invalid_utf8):
            assert response.status_code == 422
            assert response.json()["type"] == settings.problem_type_url(ProblemType.INVALID_REQUEST)
            assert response.json()["errors"] == [{"pointer": "/", "reason": "Request body must be valid JSON."}]

        assert openapi.status_code == 200
        login_responses = openapi.json()["paths"]["/api/v1/auth/login"]["post"]["responses"]
        assert "application/problem+json" in login_responses["422"]["content"]
        assert "ProblemDetails" in openapi.json()["components"]["schemas"]

    asyncio.run(scenario())
