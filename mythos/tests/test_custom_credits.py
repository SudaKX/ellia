import asyncio
from importlib import import_module
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.auth.tokens import decode_access_token
from mythos.core.config import Settings
from mythos.core.file_ids import FileIdCodec
from mythos.main import create_app
from mythos.persistence.base import Base
from mythos.persistence.models import (
    PlayerCreditBalance,
    PlayerCreditState,
    PlayerProgress,
    PlayerRecord,
)
from mythos.players.interfaces import (
    InsufficientCreditsError,
    PlayerInterfaces,
    UnknownCreditError,
)
from mythos.players.loader import PlayerLoader
from mythos.registry.bundle import RegistryBundle
from mythos.registry.credits import CREDIT_VTB_ID, CreditTemplate
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.files import FileReference, ObjectReference
from mythos.registry.hints import Hint, HintDisplayParams
from mythos.registry.progress import NormalProgressNode

pytestmark = pytest.mark.anyio

_FILE_IDS = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")


def test_custom_credits_migration_is_irreversible() -> None:
    migration = import_module("migrations.versions.0013_custom_credits")

    with pytest.raises(NotImplementedError, match="forbidden"):
        migration.downgrade()


def test_credit_registry_registers_freezes_and_injects_builtin_vtb() -> None:
    registry = RegistryBundle().credits
    registry.register_template(CreditTemplate("test.coins", "Coins"))

    with pytest.raises(DuplicateStableIdError):
        registry.register_template(CreditTemplate("test.coins", "Coins again"))

    registry.ensure_builtin_vtb()
    catalog = registry.freeze()
    assert catalog.credit_ids == frozenset({"test.coins", CREDIT_VTB_ID})
    assert catalog.template(CREDIT_VTB_ID).display_name == "VTB"
    assert catalog.template_version.startswith("cc1_")

    with pytest.raises(RegistryFrozenError):
        registry.register_template(CreditTemplate("test.late", "Late"))


def test_bundle_freeze_rejects_hint_with_unregistered_credit() -> None:
    registries = RegistryBundle()
    registries.progress.register(NormalProgressNode("start", (), is_entry=True))
    registries.hints.register(
        Hint(
            stable_id="test.hint",
            source=FileReference("test", "assets/hint.txt", "text/plain; charset=utf-8"),
            download_name="hint.txt",
            display=HintDisplayParams(title="Hint"),
            credit_id="test.missing",
            credit_amount=3,
        )
    )
    registries.hints.materialize_static_content(
        {
            "test:assets/hint.txt": ObjectReference(
                "static/test/assets/hint.txt",
                "sha256:" + "a" * 64,
                "text/plain; charset=utf-8",
                4,
            )
        }
    )

    with pytest.raises(RegistryError, match="unregistered credit"):
        registries.freeze(_FILE_IDS)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as current:
        yield current
    await engine.dispose()


def _catalogs_with_coins():
    registries = RegistryBundle()
    registries.credits.register_template(CreditTemplate("test.coins", "Coins"))
    return registries.freeze(_FILE_IDS)


async def test_credit_interface_grant_spend_balances_and_aggregate_version(session) -> None:
    catalogs = _catalogs_with_coins()
    loader = PlayerLoader(catalogs, FakeObjectStore(), _FILE_IDS)
    player_id = uuid4()
    session.add(
        PlayerRecord(id=player_id, username=str(player_id), username_normalized=str(player_id))
    )
    await session.commit()

    player = await loader.load(
        session, player_id, writable=True, interfaces=PlayerInterfaces.CREDITS
    )
    credits = player.credits
    assert credits.version == 0
    assert credits.balance(CREDIT_VTB_ID) == 0
    assert credits.balance("test.coins") == 0
    assert [balance.body() for balance in credits.balances] == [
        {"credit_id": "test.coins", "balance": 0},
        {"credit_id": "vtb", "balance": 0},
    ]

    assert await credits.grant("test.coins", 5) == 5
    assert credits.balance("test.coins") == 5
    assert credits.version == 1

    assert await credits.try_spend("test.coins", 3) == 2
    assert credits.balance("test.coins") == 2
    assert credits.version == 2

    with pytest.raises(InsufficientCreditsError):
        await credits.try_spend("test.coins", 3)
    assert credits.balance("test.coins") == 2
    assert credits.version == 2

    with pytest.raises(UnknownCreditError):
        await credits.grant("test.missing", 1)
    with pytest.raises(UnknownCreditError):
        credits.balance("test.missing")

    assert await credits.remove_unregistered(frozenset({"test.coins"})) is True
    assert credits.version == 3
    assert credits.balance("test.coins") == 0
    assert [balance.body() for balance in credits.balances] == [
        {"credit_id": "test.coins", "balance": 0},
        {"credit_id": "vtb", "balance": 0},
    ]


async def test_credit_interface_grants_vtb_and_unknown_rows_are_rejected(session) -> None:
    catalogs = _catalogs_with_coins()
    loader = PlayerLoader(catalogs, FakeObjectStore(), _FILE_IDS)
    player_id = uuid4()
    session.add(
        PlayerRecord(id=player_id, username=str(player_id), username_normalized=str(player_id))
    )
    await session.commit()

    player = await loader.load(
        session, player_id, writable=True, interfaces=PlayerInterfaces.CREDITS
    )
    credits = player.credits
    versions = [credits.version]
    for amount in (1, 2, 3):
        await credits.grant(CREDIT_VTB_ID, amount)
        versions.append(credits.version)
    assert credits.balance(CREDIT_VTB_ID) == 6
    assert versions == sorted(set(versions)) and len(set(versions)) == len(versions)
    with pytest.raises(ValueError):
        await credits.grant(CREDIT_VTB_ID, 0)
    with pytest.raises(ValueError):
        await credits.try_spend(CREDIT_VTB_ID, -1)


def test_startup_credit_reconciliation_removes_stale_balances(tmp_path: Path) -> None:
    async def scenario() -> None:
        settings = Settings(
            environment="test",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'credits-reconcile.sqlite3').as_posix()}",
            checkpoint_directory=tmp_path / "checkpoints",
            jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
            refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
            file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
            refresh_cookie_secure=False,
        )

        def registries_with(*credit_ids: str) -> RegistryBundle:
            registries = RegistryBundle()
            registries.progress.register(NormalProgressNode("start", (), is_entry=True))
            for credit_id in credit_ids:
                registries.credits.register_template(CreditTemplate(credit_id, credit_id.title()))
            return registries

        first = create_app(settings, registries=registries_with("test.retired"), object_store=FakeObjectStore())
        async with first.router.lifespan_context(first):
            async with first.state.database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            transport = httpx.ASGITransport(app=first)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                registration = await client.post(
                    "/api/v1/auth/register",
                    json={"username": "credits-reconcile-player", "password": "correct-horse-battery"},
                )
            player_id = decode_access_token(registration.json()["access_token"], settings).player_id
            async with first.state.database.session_factory() as session:
                async with session.begin():
                    player = await first.state.runtime.player_loader.load_writable(
                        session, player_id, interfaces=PlayerInterfaces.CREDITS
                    )
                    await player.credits.grant("test.retired", 7)

        assert settings.credit_snapshot_path.exists()
        settings.credit_snapshot_path.unlink()

        second = create_app(settings, registries=registries_with("test.current"), object_store=FakeObjectStore())
        async with second.router.lifespan_context(second):
            async with second.state.database.session_factory() as session:
                stale = await session.scalar(
                    select(PlayerCreditBalance).where(
                        PlayerCreditBalance.player_id == player_id,
                        PlayerCreditBalance.credit_id == "test.retired",
                    )
                )
                assert stale is None
                state = await session.get(PlayerCreditState, player_id)
                assert state is not None
        assert settings.credit_snapshot_path.exists()

    asyncio.run(scenario())
