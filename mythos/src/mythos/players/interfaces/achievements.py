from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from mythos.persistence.base import utcnow
from mythos.persistence.models import PlayerAchievementState


class ReadOnlyAchievementError(Exception):
    pass


class InactiveAchievementError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AchievementStateSnapshot:
    stable_id: str
    earned_at: datetime
    claimed_at: datetime | None

    @property
    def status(self) -> str:
        return "claimed" if self.claimed_at is not None else "available"

    def body(self) -> dict[str, str | None]:
        return {
            "stable_id": self.stable_id,
            "earned_at": self.earned_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at is not None else None,
        }


class AchievementInterface:
    def __init__(
        self,
        player_id: UUID,
        session: AsyncSession,
        records: Iterable[PlayerAchievementState],
        *,
        active_stable_ids: frozenset[str],
        writable: bool,
        on_mutation: Callable[[], None] | None = None,
    ) -> None:
        self._player_id = player_id
        self._session = session
        self._writable = writable
        self._active_stable_ids = active_stable_ids
        self._on_mutation = on_mutation or (lambda: None)
        self._records_by_stable_id = {record.achievement_stable_id: record for record in records}
        self._pending_grants: set[str] = set()

    @property
    def states(self) -> tuple[AchievementStateSnapshot, ...]:
        return tuple(
            self._snapshot(record)
            for record in sorted(self._records_by_stable_id.values(), key=lambda item: item.achievement_stable_id)
        )

    def state(self, stable_id: str) -> AchievementStateSnapshot | None:
        record = self._records_by_stable_id.get(stable_id)
        return self._snapshot(record) if record is not None else None

    def has_earned(self, stable_id: str) -> bool:
        return stable_id in self._records_by_stable_id

    async def earn(self, stable_id: str, *, earned_at: datetime | None = None) -> AchievementStateSnapshot:
        self._ensure_writable()
        existing = self._records_by_stable_id.get(stable_id)
        if existing is not None:
            return self._snapshot(existing)
        now = earned_at or utcnow()
        record = PlayerAchievementState(
            player_id=self._player_id,
            achievement_stable_id=stable_id,
            earned_at=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(record)
        self._records_by_stable_id[stable_id] = record
        self._on_mutation()
        return self._snapshot(record)

    async def grant(self, stable_id: str) -> AchievementStateSnapshot:
        self._ensure_writable()
        if stable_id not in self._active_stable_ids:
            raise InactiveAchievementError("Only active achievements can be granted.")
        state = await self.earn(stable_id)
        self._pending_grants.add(stable_id)
        return state

    def drain_grants(self) -> tuple[str, ...]:
        grants = tuple(sorted(self._pending_grants))
        self._pending_grants.clear()
        return grants

    async def claim(self, stable_id: str, *, claimed_at: datetime | None = None) -> AchievementStateSnapshot | None:
        self._ensure_writable()
        record = self._records_by_stable_id.get(stable_id)
        if record is None:
            return None
        if record.claimed_at is None:
            now = claimed_at or utcnow()
            record.claimed_at = now
            record.updated_at = now
            self._on_mutation()
        return self._snapshot(record)

    @staticmethod
    def _snapshot(record: PlayerAchievementState | None) -> AchievementStateSnapshot | None:
        if record is None:
            return None
        return AchievementStateSnapshot(
            stable_id=record.achievement_stable_id,
            earned_at=record.earned_at,
            claimed_at=record.claimed_at,
        )

    def _ensure_writable(self) -> None:
        if not self._writable:
            raise ReadOnlyAchievementError("Read-only players cannot modify achievements.")
