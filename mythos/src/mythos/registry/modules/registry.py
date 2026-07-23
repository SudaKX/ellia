from __future__ import annotations

from collections import defaultdict

from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.modules.callbacks import (
    CommandCallback,
    CommandCallbackRegistration,
    ViewCallback,
    ViewCallbackRegistration,
)
from mythos.registry.modules.catalog import ModuleCatalog


class ModuleRegistry:
    def __init__(self) -> None:
        self._stable_ids: set[str] = set()
        self._views: dict[str, list[ViewCallbackRegistration]] = defaultdict(list)
        self._commands: dict[str, dict[str, CommandCallbackRegistration]] = defaultdict(dict)
        self._registration_order = 0
        self._frozen = False
        self._catalog: ModuleCatalog | None = None

    def register_view(self, endpoint_id: str, stable_id: str, callback: ViewCallback, *, priority: int = 0) -> None:
        self._ensure_mutable()
        self._reserve_stable_id(stable_id)
        self._views[endpoint_id].append(
            ViewCallbackRegistration(endpoint_id, stable_id, priority, self._next_order(), callback)
        )

    def register_command(self, endpoint_id: str, stable_id: str, callback: CommandCallback) -> None:
        self._ensure_mutable()
        self._reserve_stable_id(stable_id)
        self._commands[endpoint_id][stable_id] = CommandCallbackRegistration(endpoint_id, stable_id, callback)

    def freeze(self) -> ModuleCatalog:
        if self._catalog is not None:
            return self._catalog
        views = {
            endpoint_id: tuple(sorted(entries, key=lambda item: (item.priority, item.registration_order)))
            for endpoint_id, entries in self._views.items()
        }
        self._catalog = ModuleCatalog(views, self._commands)
        self._frozen = True
        return self._catalog

    def _reserve_stable_id(self, stable_id: str) -> None:
        if not stable_id:
            raise RegistryError("Callback stable IDs cannot be empty.")
        if stable_id in self._stable_ids:
            raise DuplicateStableIdError(stable_id)
        self._stable_ids.add(stable_id)

    def _next_order(self) -> int:
        value = self._registration_order
        self._registration_order += 1
        return value

    def _ensure_mutable(self) -> None:
        if self._frozen:
            raise RegistryFrozenError("The module registry is frozen.")
