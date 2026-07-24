from __future__ import annotations

import re

from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.validations.catalog import ValidationCatalog
from mythos.registry.validations.definitions import ValidationAttempt

_VALIDATION_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ValidationRegistry:
    def __init__(self) -> None:
        self._attempts_by_stable_id: dict[str, ValidationAttempt] = {}
        self._attempts_by_validation_id: dict[str, ValidationAttempt] = {}
        self._frozen = False
        self._catalog: ValidationCatalog | None = None

    def register_attempt(self, attempt: ValidationAttempt) -> None:
        if self._frozen:
            raise RegistryFrozenError("The validation registry is frozen.")
        if not attempt.stable_id:
            raise RegistryError("Validation attempts require a stable ID.")
        if not _VALIDATION_ID_PATTERN.fullmatch(attempt.validation_id):
            raise RegistryError("Validation IDs must be lowercase slugs up to 64 characters.")
        if attempt.stable_id in self._attempts_by_stable_id:
            raise DuplicateStableIdError(attempt.stable_id)
        if attempt.validation_id in self._attempts_by_validation_id:
            raise RegistryError("Validation IDs must be unique.")
        self._attempts_by_stable_id[attempt.stable_id] = attempt
        self._attempts_by_validation_id[attempt.validation_id] = attempt

    def freeze(self) -> ValidationCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = ValidationCatalog(self._attempts_by_validation_id)
        return self._catalog
