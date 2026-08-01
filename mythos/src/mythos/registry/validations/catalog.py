from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.errors import RegistryError
from mythos.registry.validations.definitions import ValidationAttempt


class ValidationAttemptNotFoundError(RegistryError):
    pass


class ValidationCatalog:
    def __init__(self, attempts: Mapping[str, ValidationAttempt]) -> None:
        self._attempts = dict(attempts)

    def attempt(self, validation_id: str) -> ValidationAttempt:
        try:
            return self._attempts[validation_id]
        except KeyError as error:
            raise ValidationAttemptNotFoundError(validation_id) from error
