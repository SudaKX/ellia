from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mythos.endpoints.actions import Action
from mythos.players.context import PlayerRequestContext
from mythos.registry.validations import ValidationAttempt, ValidationCatalog


class ValidationService:
    def __init__(self, catalog: ValidationCatalog) -> None:
        self._catalog = catalog

    def attempt(self, validation_id: str) -> ValidationAttempt:
        return self._catalog.attempt(validation_id)

    async def submit(
        self,
        context: PlayerRequestContext,
        attempt: ValidationAttempt,
        payload: Mapping[str, Any],
    ) -> tuple[Action, ...]:
        return await attempt.handler(context, payload)
