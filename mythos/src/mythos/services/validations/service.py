from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mythos.core.followups import ContextScope
from mythos.players.context import ValidationContext
from mythos.players.player import Player
from mythos.registry.validations import ValidationAttempt, ValidationCatalog, ValidationResult


class ValidationService:
    def __init__(self, catalog: ValidationCatalog) -> None:
        self._catalog = catalog

    def attempt(self, validation_id: str) -> ValidationAttempt:
        return self._catalog.attempt(validation_id)

    async def submit(
        self,
        player: Player,
        attempt: ValidationAttempt,
        payload: Mapping[str, Any],
        *,
        scope: ContextScope | None = None,
    ) -> ValidationResult:
        context = ValidationContext(player=player, scope=scope or ContextScope.silent())
        return await attempt.handler(context, payload)
