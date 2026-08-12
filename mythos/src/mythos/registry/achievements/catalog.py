from __future__ import annotations

from collections.abc import Mapping

from mythos.core.file_ids import FileIdCodec
from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.achievements.definitions import AchievementDefinition, AchievementFallback
from mythos.registry.catalog_snapshots import fingerprint
from mythos.registry.errors import RegistryError


class AchievementNotFoundError(RegistryError):
    pass


class AchievementCatalog:
    def __init__(
        self,
        definitions: Mapping[str, AchievementDefinition],
        file_ids: FileIdCodec,
        fallbacks: Mapping[str, AchievementFallback] | None = None,
    ) -> None:
        self._definitions = dict(definitions)
        self._fallbacks = dict(fallbacks or {})
        conflicts = set(self._definitions) & set(self._fallbacks)
        if conflicts:
            raise RegistryError(f"Achievement fallback conflicts with active achievement {next(iter(sorted(conflicts)))!r}.")
        self._file_id_key_fingerprint = file_ids.key_fingerprint
        self._public_ids_by_stable_id = {
            stable_id: file_ids.encode_achievement_id(stable_id)
            for stable_id in (*self._definitions, *self._fallbacks)
        }
        self._stable_ids_by_public_id = {
            public_id: stable_id for stable_id, public_id in self._public_ids_by_stable_id.items()
        }
        self.version = fingerprint(
            "acv1_",
            [
                {
                    "kind": "active",
                    "stable_id": stable_id,
                    "immediate": definition.immediate,
                    "meta": definition.meta_body(),
                    "dependencies": int(definition.dependencies),
                    "condition": getattr(definition.condition, "__callback_id__", None),
                    "effect": getattr(definition.effect, "__callback_id__", None),
                }
                for stable_id, definition in sorted(self._definitions.items())
            ]
            + [
                {
                    "kind": "fallback",
                    "stable_id": stable_id,
                    "immediate": fallback.immediate,
                    "meta": fallback.meta_body(),
                }
                for stable_id, fallback in sorted(self._fallbacks.items())
            ],
        )

    @property
    def file_id_key_fingerprint(self) -> str:
        return self._file_id_key_fingerprint

    @property
    def achievements(self) -> tuple[AchievementDefinition, ...]:
        return tuple(self._definitions[stable_id] for stable_id in sorted(self._definitions))

    @property
    def stable_ids(self) -> frozenset[str]:
        return frozenset(self._definitions)

    @property
    def fallbacks(self) -> tuple[AchievementFallback, ...]:
        return tuple(self._fallbacks[stable_id] for stable_id in sorted(self._fallbacks))

    @property
    def dependencies(self) -> PlayerInterfaces:
        dependencies = PlayerInterfaces.NONE
        for definition in self._definitions.values():
            dependencies |= definition.dependencies
        return dependencies

    def achievement(self, stable_id: str) -> AchievementDefinition:
        try:
            return self._definitions[stable_id]
        except KeyError as error:
            raise AchievementNotFoundError(stable_id) from error

    def achievement_or_none(self, stable_id: str) -> AchievementDefinition | None:
        return self._definitions.get(stable_id)

    def fallback(self, stable_id: str) -> AchievementFallback:
        try:
            return self._fallbacks[stable_id]
        except KeyError as error:
            raise AchievementNotFoundError(stable_id) from error

    def fallback_or_none(self, stable_id: str) -> AchievementFallback | None:
        return self._fallbacks.get(stable_id)

    def achievement_by_public_id(self, public_id: str) -> AchievementDefinition:
        try:
            return self._definitions[self._stable_ids_by_public_id[public_id]]
        except KeyError as error:
            raise AchievementNotFoundError(public_id) from error

    def public_id_for(self, stable_id: str) -> str:
        try:
            return self._public_ids_by_stable_id[stable_id]
        except KeyError as error:
            raise AchievementNotFoundError(stable_id) from error

    def fallback_by_public_id(self, public_id: str) -> AchievementFallback:
        try:
            return self._fallbacks[self._stable_ids_by_public_id[public_id]]
        except KeyError as error:
            raise AchievementNotFoundError(public_id) from error

    def stable_id_for_public_id(self, public_id: str) -> str:
        try:
            return self._stable_ids_by_public_id[public_id]
        except KeyError as error:
            raise AchievementNotFoundError(public_id) from error
