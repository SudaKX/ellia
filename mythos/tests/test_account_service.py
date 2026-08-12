import asyncio
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select

from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.core.problems import ProblemType
from mythos.eventbus import EventContext, VirtualAccountLoggedInEvent
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerVirtualAccount, PlayerVirtualAccountState
from mythos.registry.accounts import VirtualAccountTemplate
from mythos.registry.bundle import RegistryBundle
from mythos.registry.callbacks import module_handler
from mythos.players.interfaces import PlayerInterfaces


def _registries(*account_ids: str, events: list[VirtualAccountLoggedInEvent] | None = None) -> RegistryBundle:
    registries = RegistryBundle()
    for index, account_id in enumerate(account_ids):
        registries.accounts.register_template(
            VirtualAccountTemplate(
                account_id,
                f"Account {index}",
                permission=index - 1,
                metadata={"index": index},
            )
        )
    if events is not None:
        @registries.events.on(VirtualAccountLoggedInEvent)
        @module_handler("test.accounts")(1, dependencies=PlayerInterfaces.NONE)
        async def record_login(context: EventContext) -> None:
            events.append(context.event)
    return registries


def _settings(tmp_path, *, allow_empty: bool = False) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'accounts.sqlite3').as_posix()}",
        jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
        refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
        file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
        refresh_cookie_secure=False,
        virtual_account_template_snapshot_path=tmp_path / "virtual-account-templates.json",
        allow_empty_virtual_account_catalog_reconciliation=allow_empty,
    )


async def _issue(app, player_id, account_id: str, username: str, password: str, *, login: bool = False) -> None:
    async with app.state.database.session_factory() as session:
        async with session.begin():
            player = await app.state.runtime.player_loader.load(session, player_id, writable=True)
            await player.accounts.issue(account_id, username, password)
            if login:
                await player.accounts.login(username, password)


@pytest.mark.anyio
async def test_vac_routes_log_in_and_log_out_module_issued_account(tmp_path) -> None:
    events: list[VirtualAccountLoggedInEvent] = []
    settings = _settings(tmp_path)
    app = create_app(settings, registries=_registries("test.operator", events=events))

    async with app.router.lifespan_context(app):
        async with app.state.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            registration = await client.post(
                "/api/v1/auth/register",
                json={"username": "account-player", "password": "correct-horse-battery"},
            )
            assert registration.status_code == 201
            token = registration.json()["access_token"]
            player_id = decode_access_token(token, settings).player_id
            await _issue(app, player_id, "test.operator", "operator", "module-password")

            headers = {"Authorization": f"Bearer {token}", "Request-ID": str(uuid4())}
            invalid = await client.post(
                "/api/v1/vac/login",
                headers=headers,
                json={"username": "operator", "password": "wrong"},
            )
            assert invalid.status_code == 401
            assert invalid.headers["content-type"].startswith("application/problem+json")
            assert invalid.headers.get("www-authenticate") is None
            invalid_problem = invalid.json()
            assert invalid_problem == {
                "type": settings.problem_type_url(ProblemType.VIRTUAL_ACCOUNT_INVALID_CREDENTIALS),
                "title": "Invalid virtual account credentials",
                "status": 401,
                "detail": "The supplied virtual account credentials are invalid.",
                "instance": invalid_problem["instance"],
            }
            assert invalid_problem["instance"].startswith("urn:uuid:")
            assert events == []

            malformed = await client.post(
                "/api/v1/vac/login",
                headers={"Authorization": f"Bearer {token}", "Request-ID": str(uuid4())},
                json={"username": "operator", "password": "x" * 129},
            )
            assert malformed.status_code == 422
            assert malformed.headers["content-type"].startswith("application/problem+json")
            assert malformed.json()["type"] == settings.problem_type_url(ProblemType.INVALID_REQUEST)
            assert malformed.json()["errors"]
            assert "x" * 129 not in malformed.text

            logged_in = await client.post(
                "/api/v1/vac/login",
                headers={"Authorization": f"Bearer {token}", "Request-ID": str(uuid4())},
                json={"username": "OPERATOR", "password": "module-password"},
            )
            assert logged_in.status_code == 200
            current = logged_in.json()["content"]["current_account"]
            assert current["account_id"] == "test.operator"
            assert current["permission"] == -1
            assert current["metadata"] == {"index": 0}
            assert current["login_count"] == 1
            assert [(event.player_id, event.account_id) for event in events] == [(player_id, "test.operator")]

            logged_out = await client.post(
                "/api/v1/vac/logout",
                headers={"Authorization": f"Bearer {token}", "Request-ID": str(uuid4())},
            )
            assert logged_out.status_code == 200
            assert logged_out.json()["content"]["current_account"] is None


@pytest.mark.anyio
async def test_startup_reconciliation_removes_sql_accounts_absent_from_catalog_after_snapshot_loss(tmp_path) -> None:
    settings = _settings(tmp_path)
    first = create_app(settings, registries=_registries("test.retired"))

    async with first.router.lifespan_context(first):
        async with first.state.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        transport = httpx.ASGITransport(app=first)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            registration = await client.post(
                "/api/v1/auth/register",
                json={"username": "reconciliation-player", "password": "correct-horse-battery"},
            )
        player_id = decode_access_token(registration.json()["access_token"], settings).player_id
        await _issue(first, player_id, "test.retired", "retired", "password", login=True)

    assert settings.virtual_account_snapshot_path.exists()
    settings.virtual_account_snapshot_path.unlink()
    second = create_app(settings, registries=_registries("test.current"))

    async with second.router.lifespan_context(second):
        async with second.state.database.session_factory() as session:
            assert await session.get(PlayerVirtualAccount, (player_id, "test.retired")) is None
            state = await session.get(PlayerVirtualAccountState, player_id)
            assert state is not None
            assert state.current_account_id is None
            assert state.version == 3
            assert tuple((await session.scalars(select(PlayerVirtualAccount))).all()) == ()
    assert settings.virtual_account_snapshot_path.exists()
