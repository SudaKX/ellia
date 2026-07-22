from __future__ import annotations

from collections.abc import Iterable

from mythos.players.effects import PendingEffect


class PendingEffectPlan:
    def __init__(self) -> None:
        self._effects: list[PendingEffect] = []
        self._frozen = False

    def add(self, effect: PendingEffect) -> PendingEffectPlan:
        self._ensure_mutable()
        self._ensure_framework_effect(effect)
        self._effects.append(effect)
        return self

    def extend(self, effects: Iterable[PendingEffect]) -> PendingEffectPlan:
        self._ensure_mutable()
        prepared = tuple(effects)
        for effect in prepared:
            self._ensure_framework_effect(effect)
        self._effects.extend(prepared)
        return self

    def freeze(self) -> tuple[PendingEffect, ...]:
        self._frozen = True
        return tuple(self._effects)

    def _ensure_mutable(self) -> None:
        if self._frozen:
            raise RuntimeError("PendingEffectPlan is already owned by an EffectAction.")

    @staticmethod
    def _ensure_framework_effect(effect: PendingEffect) -> None:
        from mythos.players.effects import SetCheckpointEffect

        if type(effect) is not SetCheckpointEffect:
            raise TypeError("PendingEffectPlan only accepts framework-provided effect types.")
