from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mythos.players.context import CommandContext
from mythos.registry.validations import ValidationAttempt, ValidationCatalog, ValidationOutcome


class ValidationService:
    def __init__(self, catalog: ValidationCatalog) -> None:
        self._catalog = catalog

    def attempt(self, validation_id: str) -> ValidationAttempt:
        return self._catalog.attempt(validation_id)

    async def submit(
        self,
        context: CommandContext,
        attempt: ValidationAttempt,
        payload: Mapping[str, Any],
    ) -> ValidationOutcome:
        return await attempt.handler(context, payload)
