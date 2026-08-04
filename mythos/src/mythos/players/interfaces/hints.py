from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.base import utcnow
from mythos.persistence.models.hints import PlayerHintDisclosure


class ReadOnlyHintsError(Exception):
    pass


@dataclass(frozen=True)
class HintDisclosure:
    hint_stable_id: str
    disclosed_at: datetime


@dataclass(frozen=True)
class HintClaim:
    disclosure: HintDisclosure
    created: bool


class HintInterface:
    def __init__(
        self,
        player_id: UUID,
        session: AsyncSession,
        disclosures: tuple[PlayerHintDisclosure, ...],
        *,
        writable: bool,
    ) -> None:
        self._player_id = player_id
        self._session = session
        self._writable = writable
        self._disclosures_by_stable_id = {
            disclosure.hint_stable_id: HintDisclosure(
                hint_stable_id=disclosure.hint_stable_id,
                disclosed_at=disclosure.disclosed_at,
            )
            for disclosure in disclosures
        }

    @property
    def disclosures(self) -> tuple[HintDisclosure, ...]:
        return tuple(sorted(self._disclosures_by_stable_id.values(), key=lambda item: item.disclosed_at))

    def disclosed(self, hint_stable_id: str) -> HintDisclosure | None:
        return self._disclosures_by_stable_id.get(hint_stable_id)

    async def claim(self, hint_stable_id: str) -> HintClaim:
        self._ensure_writable()
        existing = self.disclosed(hint_stable_id)
        if existing is not None:
            return HintClaim(existing, created=False)
        disclosed_at = utcnow()
        try:
            async with self._session.begin_nested():
                record = PlayerHintDisclosure(
                    player_id=self._player_id,
                    hint_stable_id=hint_stable_id,
                    disclosed_at=disclosed_at,
                )
                self._session.add(record)
                await self._session.flush()
        except IntegrityError:
            record = await self._session.get(PlayerHintDisclosure, (self._player_id, hint_stable_id))
            if record is None:
                raise RuntimeError("Hint disclosure claim was not persisted.")
            disclosure = HintDisclosure(hint_stable_id=record.hint_stable_id, disclosed_at=record.disclosed_at)
            self._disclosures_by_stable_id[hint_stable_id] = disclosure
            return HintClaim(disclosure, created=False)
        disclosure = HintDisclosure(hint_stable_id=hint_stable_id, disclosed_at=disclosed_at)
        self._disclosures_by_stable_id[hint_stable_id] = disclosure
        return HintClaim(disclosure, created=True)

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyHintsError("Read-only players cannot modify hint disclosures.")
