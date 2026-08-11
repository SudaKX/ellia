from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.achievements.catalog import AchievementCatalog
from mythos.registry.achievements.definitions import AchievementDefinition, AchievementFallback
from mythos.registry.callbacks import callback_dependencies, validate_callback
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.core.file_ids import FileIdCodec


class AchievementRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, AchievementDefinition] = {}
        self._fallbacks: dict[str, AchievementFallback] = {}
        self._frozen = False
        self._catalog: AchievementCatalog | None = None

    def register(self, definition: AchievementDefinition) -> None:
        self._ensure_mutable()
        if not isinstance(definition, AchievementDefinition):
            raise RegistryError("Achievement registrations require an AchievementDefinition.")
        if definition.stable_id in self._definitions:
            raise DuplicateStableIdError(definition.stable_id)
        try:
            validate_callback(
                definition.condition,
                field_name="Achievement condition",
                parameter_count=1,
                asynchronous=False,
                require_dependencies=True,
            )
            validate_callback(
                definition.effect,
                field_name="Achievement effect",
                parameter_count=1,
                asynchronous=True,
                require_dependencies=True,
            )
            condition_dependencies = callback_dependencies(
                definition.condition,
                field_name="Achievement condition",
                required=True,
            )
            effect_dependencies = callback_dependencies(
                definition.effect,
                field_name="Achievement effect",
                required=True,
            )
        except ValueError as error:
            raise RegistryError(f"Invalid achievement definition for {definition.stable_id!r}.") from error
        dependencies = (condition_dependencies or PlayerInterfaces.NONE) | (
            effect_dependencies or PlayerInterfaces.NONE
        )
        object.__setattr__(definition, "dependencies", dependencies)
        self._definitions[definition.stable_id] = definition

    def set_fallback(self, stable_id: str, meta: Mapping[str, Any], immediate: bool) -> None:
        self._ensure_mutable()
        fallback = AchievementFallback(stable_id=stable_id, meta=meta, immediate=immediate)
        self._fallbacks[stable_id] = fallback

    def freeze(self, file_ids: FileIdCodec) -> AchievementCatalog:
        if self._catalog is not None:
            if self._catalog.file_id_key_fingerprint != file_ids.key_fingerprint:
                raise RegistryError("Achievement registry is already frozen with a different file ID key.")
            return self._catalog
        catalog = AchievementCatalog(self._definitions, file_ids, self._fallbacks)
        self._frozen = True
        self._catalog = catalog
        return self._catalog

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The achievement registry is frozen.")
