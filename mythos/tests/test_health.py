import asyncio

import httpx

from mythos.main import app


def test_healthcheck_returns_ok() -> None:
    async def request_healthcheck() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/health")

    response = asyncio.run(request_healthcheck())

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
