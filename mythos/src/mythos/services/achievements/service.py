from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from mythos.core.file_ids import FileIdCodec
from mythos.players.interfaces import AchievementStateSnapshot
from mythos.players.player import Player
from mythos.registry.achievements import AchievementCatalog, AchievementDefinition
from mythos.registry.errors import RegistryError


class AchievementStatus(StrEnum):
    LOCKED = "locked"
    AVAILABLE = "available"
    CLAIMED = "claimed"
    DELETED = "deleted"
    MISSING_FALLBACK = "missing-fallback"


class AchievementDeletedError(Exception):
    pass


class AchievementNotAvailableError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class AchievementSnapshot:
    stable_id: str
    public_id: str
    meta: Mapping[str, Any]
    immediate: bool
    status: AchievementStatus
    earned_at: object | None = None
    claimed_at: object | None = None

    def body(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "public_id": self.public_id,
            "meta": _copy_json(self.meta),
            "immediate": self.immediate,
            "status": self.status.value,
        }
        if self.earned_at is not None:
            body["earned_at"] = self.earned_at.isoformat()
        if self.claimed_at is not None:
            body["claimed_at"] = self.claimed_at.isoformat()
        return body


@dataclass(frozen=True, slots=True)
class AchievementCheckResult:
    checked_count: int
    earned_stable_ids: tuple[str, ...]
    effect_stable_ids: tuple[str, ...]

    def body(self, catalog: AchievementCatalog) -> dict[str, Any]:
        return {
            "checked": self.checked_count,
            "earned": [catalog.public_id_for(stable_id) for stable_id in self.earned_stable_ids],
            "effects": [catalog.public_id_for(stable_id) for stable_id in self.effect_stable_ids],
        }


class AchievementService:
    def __init__(self, catalog: AchievementCatalog, file_ids: FileIdCodec) -> None:
        self._catalog = catalog
        self._file_ids = file_ids

    @property
    def catalog(self) -> AchievementCatalog:
        return self._catalog

    def snapshots(self, player: Player) -> tuple[AchievementSnapshot, ...]:
        states = {state.stable_id: state for state in player.achievements.states}
        items = [self._active_snapshot(definition, states.get(definition.stable_id)) for definition in self._catalog.achievements]
        active_ids = self._catalog.stable_ids
        for stable_id in sorted(states.keys() - active_ids):
            state = states[stable_id]
            fallback = self._catalog.fallback_or_none(stable_id)
            if fallback is None:
                items.append(
                    AchievementSnapshot(
                        stable_id=stable_id,
                        public_id=self._file_ids.encode_achievement_id(stable_id),
                        meta=MappingProxyType({}),
                        immediate=False,
                        status=AchievementStatus.MISSING_FALLBACK,
                        earned_at=state.earned_at,
                        claimed_at=state.claimed_at,
                    )
                )
                continue
            items.append(
                AchievementSnapshot(
                    stable_id=stable_id,
                    public_id=self._catalog.public_id_for(stable_id),
                    meta=fallback.meta,
                    immediate=fallback.immediate,
                    status=AchievementStatus.DELETED,
                    earned_at=state.earned_at,
                    claimed_at=state.claimed_at,
                )
            )
        return tuple(items)

    async def check(self, player: Player) -> AchievementCheckResult:
        earned: list[str] = []
        effects: list[str] = []
        for definition in self._catalog.achievements:
            if definition.condition is None:
                continue
            state = player.achievements.state(definition.stable_id)
            if not definition.condition(player):
                continue
            if state is None:
                state = await player.achievements.earn(definition.stable_id)
                earned.append(definition.stable_id)
            if state.claimed_at is None and definition.immediate:
                effects.append(definition.stable_id)
        return AchievementCheckResult(
            checked_count=sum(definition.condition is not None for definition in self._catalog.achievements),
            earned_stable_ids=tuple(earned),
            effect_stable_ids=tuple(effects),
        )

    def immediate_effect_candidates(self, stable_ids: Iterable[str]) -> tuple[str, ...]:
        requested = frozenset(stable_ids)
        return tuple(
            definition.stable_id
            for definition in self._catalog.achievements
            if definition.immediate and definition.stable_id in requested
        )

    async def apply_effects(self, player: Player, stable_ids: Iterable[str]) -> tuple[str, ...]:
        applied: list[str] = []
        for stable_id in stable_ids:
            definition = self._catalog.achievement(stable_id)
            state = player.achievements.state(stable_id)
            if state is None or state.claimed_at is not None:
                continue
            await definition.effect(player)
            await player.achievements.claim(stable_id)
            applied.append(stable_id)
        return tuple(applied)

    async def claim(self, player: Player, public_id: str) -> AchievementSnapshot:
        try:
            definition = self._catalog.achievement_by_public_id(public_id)
        except RegistryError as error:
            if any(
                state.stable_id not in self._catalog.stable_ids
                and self._file_ids.encode_achievement_id(state.stable_id) == public_id
                for state in player.achievements.states
            ):
                raise AchievementDeletedError("Deleted achievements cannot be claimed.") from error
            raise AchievementNotAvailableError("The requested achievement is not available.") from error
        state = player.achievements.state(definition.stable_id)
        if state is None:
            raise AchievementNotAvailableError("The requested achievement has not been earned.")
        if state.claimed_at is None:
            await definition.effect(player)
            await player.achievements.claim(definition.stable_id)
        state = player.achievements.state(definition.stable_id)
        if state is None:
            raise RuntimeError("Achievement claim was not persisted.")
        return self._active_snapshot(definition, state)

    def _active_snapshot(
        self,
        definition: AchievementDefinition,
        state: AchievementStateSnapshot | None,
    ) -> AchievementSnapshot:
        status = AchievementStatus.LOCKED
        earned_at = None
        claimed_at = None
        if state is not None:
            status = AchievementStatus.CLAIMED if state.claimed_at is not None else AchievementStatus.AVAILABLE
            earned_at = state.earned_at
            claimed_at = state.claimed_at
        return AchievementSnapshot(
            stable_id=definition.stable_id,
            public_id=self._catalog.public_id_for(definition.stable_id),
            meta=definition.meta,
            immediate=definition.immediate,
            status=status,
            earned_at=earned_at,
            claimed_at=claimed_at,
        )


def _copy_json(value: Mapping[str, Any]) -> dict[str, Any]:
    def thaw(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {key: thaw(child) for key, child in item.items()}
        if isinstance(item, tuple):
            return [thaw(child) for child in item]
        return item

    result = thaw(value)
    if not isinstance(result, dict):
        raise ValueError("Achievement meta must be a JSON object.")
    return result
