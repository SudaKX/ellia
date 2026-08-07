from __future__ import annotations

import asyncio
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.auth.passwords import password_hasher
from mythos.persistence.base import utcnow
from mythos.persistence.models.accounts import PlayerVirtualAccount, PlayerVirtualAccountState
from mythos.registry.accounts.catalog import VirtualAccountCatalog
from mythos.registry.accounts.definitions import VirtualAccountTemplate
from mythos.registry.errors import RegistryError


class ReadOnlyAccountError(Exception):
    pass


class AccountAlreadyIssuedError(Exception):
    pass


class AccountUsernameConflictError(Exception):
    pass


class InvalidAccountCredentialsError(Exception):
    pass


@dataclass(frozen=True)
class Account:
    account_id: str
    username: str
    display_name: str
    permission: int
    metadata: Mapping[str, object]
    created_at: datetime
    last_logged_in_at: datetime | None
    login_count: int

    def body(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "username": self.username,
            "display_name": self.display_name,
            "permission": self.permission,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
            "last_logged_in_at": (
                self.last_logged_in_at.isoformat() if self.last_logged_in_at is not None else None
            ),
            "login_count": self.login_count,
        }


def normalize_account_username(value: str) -> tuple[str, str]:
    if not isinstance(value, str):
        raise ValueError("Virtual account usernames must be strings.")
    username = unicodedata.normalize("NFKC", value.strip())
    if not 1 <= len(username) <= 32:
        raise ValueError("Virtual account usernames must contain between one and 32 characters.")
    if any(character.isspace() or ord(character) < 32 for character in username):
        raise ValueError("Virtual account usernames cannot contain whitespace or control characters.")
    normalized_username = username.casefold()
    if len(normalized_username) > 32:
        raise ValueError("Virtual account usernames must normalize to at most 32 characters.")
    return username, normalized_username


def _validate_password(value: str) -> None:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError("Virtual account passwords must contain between one and 128 characters.")


class AccountInterface:
    def __init__(
        self,
        player_id: UUID,
        catalog: VirtualAccountCatalog,
        session: AsyncSession,
        state: PlayerVirtualAccountState,
        accounts: Iterable[PlayerVirtualAccount],
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> None:
        self._player_id = player_id
        self._catalog = catalog
        self._session = session
        self._state = state
        self._writable = writable
        self._on_mutation = on_mutation or (lambda: None)
        self._accounts_by_id = {account.account_id: account for account in accounts}
        self._accounts_by_username = {
            account.username_normalized: account for account in self._accounts_by_id.values()
        }

    @property
    def version(self) -> int:
        return self._state.version or 0

    @property
    def accounts(self) -> tuple[Account, ...]:
        return tuple(
            account
            for record in sorted(self._accounts_by_id.values(), key=lambda item: item.username_normalized)
            if (account := self._view(record)) is not None
        )

    @property
    def current(self) -> Account | None:
        if self._state.current_account_id is None:
            return None
        record = self._accounts_by_id.get(self._state.current_account_id)
        return self._view(record) if record is not None else None

    def has(self, account_id: str) -> bool:
        return account_id in self._accounts_by_id and self._catalog.template_or_none(account_id) is not None

    def is_current(self, account_id: str) -> bool:
        return self._state.current_account_id == account_id and self.current is not None

    async def issue(self, account_id: str, username: str, password: str) -> Account:
        self._ensure_writable()
        try:
            template = self._catalog.template(account_id)
        except RegistryError:
            raise
        if account_id in self._accounts_by_id:
            raise AccountAlreadyIssuedError("Virtual account has already been issued.")
        canonical_username, normalized_username = normalize_account_username(username)
        if normalized_username in self._accounts_by_username:
            raise AccountUsernameConflictError("Virtual account username has already been issued.")
        _validate_password(password)
        record = PlayerVirtualAccount(
            player_id=self._player_id,
            account_id=account_id,
            username=canonical_username,
            username_normalized=normalized_username,
            password_hash=await asyncio.to_thread(password_hasher.hash, password),
            created_at=utcnow(),
            login_count=0,
        )
        self._session.add(record)
        self._accounts_by_id[account_id] = record
        self._accounts_by_username[normalized_username] = record
        self._bump_version()
        self._on_mutation()
        return self._view_with_template(record, template)

    async def delete(self, account_id: str) -> bool:
        self._ensure_writable()
        record = self._accounts_by_id.get(account_id)
        if record is None:
            return False
        await self._remove_records((record,))
        return True

    async def login(self, username: str, password: str) -> Account:
        self._ensure_writable()
        try:
            _, normalized_username = normalize_account_username(username)
            _validate_password(password)
        except ValueError as error:
            raise InvalidAccountCredentialsError from error
        record = self._accounts_by_username.get(normalized_username)
        if record is None:
            raise InvalidAccountCredentialsError
        template = self._catalog.template_or_none(record.account_id)
        if template is None:
            await self._remove_records((record,))
            raise InvalidAccountCredentialsError
        is_valid = await asyncio.to_thread(password_hasher.verify, password, record.password_hash)
        if not is_valid:
            raise InvalidAccountCredentialsError
        record.last_logged_in_at = utcnow()
        record.login_count = (record.login_count or 0) + 1
        self._state.current_account_id = record.account_id
        self._bump_version()
        self._on_mutation()
        return self._view_with_template(record, template)

    async def logout(self) -> bool:
        self._ensure_writable()
        if self._state.current_account_id is None:
            return False
        self._state.current_account_id = None
        self._bump_version()
        self._on_mutation()
        return True

    async def remove_unregistered(self, account_ids: frozenset[str]) -> bool:
        self._ensure_writable()
        records = tuple(
            record for account_id, record in self._accounts_by_id.items() if account_id in account_ids
        )
        if not records:
            return False
        await self._remove_records(records)
        return True

    async def _remove_records(self, records: tuple[PlayerVirtualAccount, ...]) -> None:
        removed_ids = {record.account_id for record in records}
        if self._state.current_account_id in removed_ids:
            self._state.current_account_id = None
            await self._session.flush()
        for record in records:
            await self._session.delete(record)
            self._accounts_by_id.pop(record.account_id, None)
            self._accounts_by_username.pop(record.username_normalized, None)
        self._bump_version()
        self._on_mutation()

    def _view(self, record: PlayerVirtualAccount) -> Account | None:
        template = self._catalog.template_or_none(record.account_id)
        return self._view_with_template(record, template) if template is not None else None

    @staticmethod
    def _view_with_template(record: PlayerVirtualAccount, template: VirtualAccountTemplate) -> Account:
        return Account(
            account_id=record.account_id,
            username=record.username,
            display_name=template.display_name,
            permission=template.permission,
            metadata=MappingProxyType(dict(template.metadata)),
            created_at=record.created_at,
            last_logged_in_at=record.last_logged_in_at,
            login_count=record.login_count,
        )

    def _bump_version(self) -> None:
        self._state.version = self.version + 1

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyAccountError("Read-only players cannot modify virtual accounts.")
