from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.base import utcnow
from mythos.persistence.models.credits import PlayerCreditBalance, PlayerCreditState
from mythos.registry.credits import CreditCatalog


class ReadOnlyCreditsError(Exception):
    pass


class InsufficientCreditsError(Exception):
    pass


class UnknownCreditError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CreditBalance:
    credit_id: str
    balance: int

    def body(self) -> dict[str, object]:
        return {"credit_id": self.credit_id, "balance": self.balance}


class CreditInterface:
    def __init__(
        self,
        player_id: UUID,
        catalog: CreditCatalog,
        session: AsyncSession,
        state: PlayerCreditState,
        balances: Iterable[PlayerCreditBalance],
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
        self._balances_by_id: dict[str, PlayerCreditBalance] = {
            balance.credit_id: balance for balance in balances
        }

    @property
    def version(self) -> int:
        return self._state.version or 0

    @property
    def balances(self) -> tuple[CreditBalance, ...]:
        return tuple(
            CreditBalance(
                credit_id,
                self._balances_by_id[credit_id].balance or 0 if credit_id in self._balances_by_id else 0,
            )
            for credit_id in sorted(self._catalog.credit_ids)
        )

    def balance(self, credit_id: str) -> int:
        self._ensure_registered(credit_id)
        row = self._balances_by_id.get(credit_id)
        return row.balance or 0 if row is not None else 0

    async def grant(self, credit_id: str, amount: int) -> int:
        return await self._mutate(credit_id, amount, spend=False)

    async def try_spend(self, credit_id: str, amount: int) -> int:
        return await self._mutate(credit_id, amount, spend=True)

    async def remove_unregistered(self, credit_ids: Iterable[str]) -> bool:
        self._ensure_writable()
        removed = False
        for credit_id in tuple(credit_ids):
            row = self._balances_by_id.pop(credit_id, None)
            if row is not None:
                await self._session.delete(row)
                removed = True
        if removed:
            await self._bump_state_version()
            self._on_mutation()
        return removed

    async def _mutate(self, credit_id: str, amount: int, *, spend: bool) -> int:
        self._ensure_writable()
        self._ensure_registered(credit_id)
        self._validate_amount(amount)
        now = utcnow()
        if credit_id not in self._balances_by_id:
            if spend:
                raise InsufficientCreditsError
            row = PlayerCreditBalance(
                player_id=self._player_id,
                credit_id=credit_id,
                balance=0,
                version=0,
                updated_at=now,
            )
            self._session.add(row)
            await self._session.flush()
            self._balances_by_id[credit_id] = row
        delta = -amount if spend else amount
        condition = PlayerCreditBalance.balance >= amount if spend else None
        statement = (
            update(PlayerCreditBalance)
            .where(PlayerCreditBalance.player_id == self._player_id, PlayerCreditBalance.credit_id == credit_id)
            .values(
                {
                    "balance": PlayerCreditBalance.balance + delta,
                    "version": PlayerCreditBalance.version + 1,
                    "updated_at": now,
                }
            )
            .returning(PlayerCreditBalance.balance, PlayerCreditBalance.version)
        )
        if condition is not None:
            statement = statement.where(condition)
        result = await self._session.execute(statement)
        row = result.one_or_none()
        if row is None:
            raise InsufficientCreditsError
        current, version = row
        balance_row = self._balances_by_id[credit_id]
        balance_row.balance = current
        balance_row.version = version
        balance_row.updated_at = now
        await self._bump_state_version()
        self._on_mutation()
        return current

    async def _bump_state_version(self) -> None:
        result = await self._session.execute(
            update(PlayerCreditState)
            .where(PlayerCreditState.player_id == self._player_id)
            .values({"version": PlayerCreditState.version + 1})
            .returning(PlayerCreditState.version)
        )
        self._state.version = result.scalar_one()

    def _ensure_registered(self, credit_id: str) -> None:
        if self._catalog.template_or_none(credit_id) is None:
            raise UnknownCreditError(f"Unknown credit ID: {credit_id!r}")

    @staticmethod
    def _validate_amount(amount: int) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("Credit amounts must be positive integers.")

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyCreditsError("Read-only players cannot modify credits.")
