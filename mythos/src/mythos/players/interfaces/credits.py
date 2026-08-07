from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.base import utcnow
from mythos.persistence.models.credits import PlayerCredits


class PlayerCreditKind(StrEnum):
    VTB = "vtb"


class ReadOnlyCreditsError(Exception):
    pass


class InsufficientCreditsError(Exception):
    pass


_CREDIT_COLUMNS = {PlayerCreditKind.VTB: PlayerCredits.vtb}


class CreditInterface:
    def __init__(
        self,
        player_id: UUID,
        session: AsyncSession,
        credits: PlayerCredits,
        *,
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> None:
        self._player_id = player_id
        self._session = session
        self._credits = credits
        self._writable = writable
        self._on_mutation = on_mutation or (lambda: None)

    @property
    def vtb(self) -> int:
        return self._credits.vtb

    @property
    def version(self) -> int:
        return self._credits.version

    async def grant_vtb(self, amount: int) -> int:
        return await self._grant(PlayerCreditKind.VTB, amount)

    async def try_spend_vtb(self, amount: int) -> int:
        return await self._try_spend(PlayerCreditKind.VTB, amount)

    async def _grant(self, kind: PlayerCreditKind, amount: int) -> int:
        self._ensure_writable()
        self._validate_amount(amount)
        column = _CREDIT_COLUMNS[kind]
        now = utcnow()
        result = await self._session.execute(
            update(PlayerCredits)
            .where(PlayerCredits.player_id == self._player_id)
            .values(
                {
                    column.key: column + amount,
                    "version": PlayerCredits.version + 1,
                    "updated_at": now,
                }
            )
            .returning(column, PlayerCredits.version)
        )
        current, version = result.one()
        setattr(self._credits, kind.value, current)
        self._credits.version = version
        self._credits.updated_at = now
        self._on_mutation()
        return current

    async def _try_spend(self, kind: PlayerCreditKind, amount: int) -> int:
        self._ensure_writable()
        self._validate_amount(amount)
        column = _CREDIT_COLUMNS[kind]
        now = utcnow()
        result = await self._session.execute(
            update(PlayerCredits)
            .where(PlayerCredits.player_id == self._player_id, column >= amount)
            .values(
                {
                    column.key: column - amount,
                    "version": PlayerCredits.version + 1,
                    "updated_at": now,
                }
            )
            .returning(column, PlayerCredits.version)
        )
        row = result.one_or_none()
        if row is None:
            raise InsufficientCreditsError
        current, version = row
        setattr(self._credits, kind.value, current)
        self._credits.version = version
        self._credits.updated_at = now
        self._on_mutation()
        return current

    @staticmethod
    def _validate_amount(amount: int) -> None:
        if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            raise ValueError("Credit amounts must be positive integers.")

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyCreditsError("Read-only players cannot modify credits.")
