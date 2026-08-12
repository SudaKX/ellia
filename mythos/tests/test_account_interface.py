import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.anyio

from mythos.auth.passwords import password_hasher
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerRecord, PlayerVirtualAccount, PlayerVirtualAccountState
from mythos.players.interfaces.accounts import (
    AccountAlreadyIssuedError,
    AccountInterface,
    AccountUsernameConflictError,
    InvalidAccountCredentialsError,
    ReadOnlyAccountError,
)
from mythos.registry.accounts import VirtualAccountRegistry, VirtualAccountTemplate


def _catalog():
    registry = VirtualAccountRegistry()
    registry.register_template(
        VirtualAccountTemplate("test.operator", "Operator", permission=7, metadata={"role": "ops"})
    )
    registry.register_template(
        VirtualAccountTemplate("test.analyst", "Analyst", permission=-3, metadata={})
    )
    registry.register_template(VirtualAccountTemplate("test.viewer", "Viewer", permission=0))
    return registry.freeze()


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _interface(session, *, writable: bool = True):
    player_id = uuid4()
    session.add(
        PlayerRecord(
            id=player_id,
            username="account-player",
            username_normalized=f"account-player-{player_id}",
        )
    )
    state = PlayerVirtualAccountState(player_id=player_id)
    session.add(state)
    return AccountInterface(player_id, _catalog(), session, state, (), writable=writable)


async def test_issue_allows_repeated_passwords_but_not_duplicate_usernames(session) -> None:
    accounts = await _interface(session)

    operator = await accounts.issue("test.operator", "Operator", "same-password")
    analyst = await accounts.issue("test.analyst", "analyst", "same-password")

    assert operator.permission == 7
    assert analyst.permission == -3
    assert accounts.version == 2
    with pytest.raises(AccountAlreadyIssuedError):
        await accounts.issue("test.operator", "other", "different")
    with pytest.raises(AccountUsernameConflictError):
        await accounts.issue("test.viewer", "OPERATOR", "different")

    await session.commit()
    rows = tuple((await session.scalars(select(PlayerVirtualAccount))).all())
    assert len(rows) == 2
    assert all("same-password" not in row.password_hash for row in rows)


async def test_login_logout_and_delete_current_account(session) -> None:
    accounts = await _interface(session)
    await accounts.issue("test.operator", "operator", "password")

    account = await accounts.login("OPERATOR", "password")
    assert account.account_id == "test.operator"
    assert accounts.current is not None
    assert accounts.current.login_count == 1
    assert accounts.is_current("test.operator")

    assert await accounts.logout()
    assert accounts.current is None
    await accounts.login("operator", "password")
    assert await accounts.delete("test.operator")
    assert accounts.current is None
    assert accounts.accounts == ()


async def test_login_removes_account_missing_from_catalog_and_raises_generic_credentials_error(session) -> None:
    accounts = await _interface(session)
    stale = PlayerVirtualAccount(
        player_id=accounts._player_id,
        account_id="removed.account",
        username="removed",
        username_normalized="removed",
        password_hash=await asyncio.to_thread(password_hasher.hash, "password"),
    )
    session.add(stale)
    accounts._accounts_by_id[stale.account_id] = stale
    accounts._accounts_by_username[stale.username_normalized] = stale
    accounts._state.current_account_id = stale.account_id

    with pytest.raises(InvalidAccountCredentialsError):
        await accounts.login("removed", "password")

    await session.commit()
    assert await session.get(PlayerVirtualAccount, (accounts._player_id, "removed.account")) is None
    assert accounts.current is None


async def test_read_only_interface_rejects_mutations(session) -> None:
    accounts = await _interface(session, writable=False)

    with pytest.raises(ReadOnlyAccountError):
        await accounts.issue("test.operator", "operator", "password")


async def test_issue_rejects_usernames_that_expand_past_the_database_limit(session) -> None:
    accounts = await _interface(session)

    with pytest.raises(ValueError, match="normalize"):
        await accounts.issue("test.operator", "ß" * 32, "password")
