from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

from mythos.endpoints.actions import Action
from mythos.players.context import PlayerRequestContext

ViewCallback: TypeAlias = Callable[[PlayerRequestContext], Awaitable[tuple[Action, ...]]]
CommandCallback: TypeAlias = Callable[[PlayerRequestContext, Mapping[str, Any]], Awaitable[tuple[Action, ...]]]


class RegistryError(Exception):
    pass


class RegistryFrozenError(RegistryError):
    pass


class DuplicateStableIdError(RegistryError):
    pass


class EndpointNotFoundError(RegistryError):
    pass


class CallbackNotFoundError(RegistryError):
    pass


@dataclass(frozen=True)
class ViewCallbackRegistration:
    endpoint_id: str
    stable_id: str
    priority: int
    registration_order: int
    callback: ViewCallback


@dataclass(frozen=True)
class CommandCallbackRegistration:
    endpoint_id: str
    stable_id: str
    callback: CommandCallback


class ModuleRegistry:
    def __init__(self) -> None:
        self._stable_ids: set[str] = set()
        self._views: dict[str, list[ViewCallbackRegistration]] = defaultdict(list)
        self._commands: dict[str, dict[str, CommandCallbackRegistration]] = defaultdict(dict)
        self._registration_order = 0
        self._frozen = False

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

    def freeze(self) -> None:
        if self._frozen:
            return
        for registrations in self._views.values():
            registrations.sort(key=lambda item: (item.priority, item.registration_order))
        self._frozen = True

    def view_callbacks(self, endpoint_id: str) -> tuple[ViewCallbackRegistration, ...]:
        self._require_frozen()
        if endpoint_id not in self._views:
            raise EndpointNotFoundError(endpoint_id)
        return tuple(self._views[endpoint_id])

    def command_callback(self, endpoint_id: str, stable_id: str) -> CommandCallbackRegistration:
        self._require_frozen()
        callbacks = self._commands.get(endpoint_id)
        if callbacks is None:
            raise EndpointNotFoundError(endpoint_id)
        try:
            return callbacks[stable_id]
        except KeyError as error:
            raise CallbackNotFoundError(stable_id) from error

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

    def _require_frozen(self) -> None:
        if not self._frozen:
            raise RegistryError("The module registry must be frozen before dispatch.")


def build_module_registry() -> ModuleRegistry:
    # Puzzle modules are intentionally imported and registered explicitly in main.py.
    return ModuleRegistry()
