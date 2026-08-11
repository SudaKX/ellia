import asyncio

import httpx

from mythos.core.config import PROJECT_ROOT, Settings
from mythos.main import create_app


def test_healthcheck_returns_ok() -> None:
    async def request_healthcheck() -> httpx.Response:
        app = create_app()
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_healthcheck())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_development_serves_example_page() -> None:
    async def request_example_page() -> httpx.Response:
        settings = Settings(
            environment="development",
            puzzle_root=PROJECT_ROOT / "puzzles",
        )
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/example/")

    response = asyncio.run(request_example_page())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "示例运行时" in response.text
    assert "hints-section" in response.text


def test_development_serves_example_assets() -> None:
    async def request_example_assets() -> tuple[httpx.Response, httpx.Response]:
        settings = Settings(
            environment="development",
            puzzle_root=PROJECT_ROOT / "puzzles",
        )
        app = create_app(settings)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            stylesheet = await client.get("/example/example.css")
            script = await client.get("/example/example.js")
            return stylesheet, script

    stylesheet, script = asyncio.run(request_example_assets())

    assert stylesheet.status_code == 200
    assert "body {" in stylesheet.text
    assert script.status_code == 200
    assert 'const API_BASE = "/api/v1";' in script.text
    assert 'callApi("/files/d/tree?path=/")' in script.text
