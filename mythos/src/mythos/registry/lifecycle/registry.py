from __future__ import annotations

from collections.abc import Callable

from mythos.registry.errors import RegistryError, RegistryFrozenError
from mythos.registry.lifecycle.catalog import LifecycleCatalog, LifecycleRegistration
from mythos.registry.lifecycle.definitions import LifecycleEventKind, LifecycleHandler, LifecyclePriority


class LifecycleRegistry:
    def __init__(self) -> None:
        self._registrations: dict[LifecycleEventKind, list[LifecycleRegistration]] = {
            event: [] for event in LifecycleEventKind
        }
        self._sequence = 0
        self._frozen = False
        self._catalog: LifecycleCatalog | None = None
        self.on_construct = self._decorator_factory(LifecycleEventKind.CONSTRUCT)
        self.on_deconstruct = self._decorator_factory(LifecycleEventKind.DECONSTRUCT)

    def register_lifecycle(
        self,
        event: LifecycleEventKind,
        handler: LifecycleHandler,
        priority: LifecyclePriority = LifecyclePriority.DEFAULT,
    ) -> None:
        self._ensure_mutable()
        if not isinstance(event, LifecycleEventKind):
            raise RegistryError("Lifecycle registrations require a lifecycle event kind.")
        if not callable(handler):
            raise RegistryError("Lifecycle registrations require a callable handler.")
        if not isinstance(priority, LifecyclePriority):
            raise RegistryError("Lifecycle registrations require a lifecycle priority.")

        registrations = self._registrations[event]
        if any(registered_handler is handler for _priority, _sequence, registered_handler in registrations):
            raise RegistryError("Lifecycle handlers may only be registered once per event.")

        registrations.append((priority, self._sequence, handler))
        self._sequence += 1

    def freeze(self) -> LifecycleCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = LifecycleCatalog(self._registrations)
        return self._catalog

    def _decorator_factory(
        self,
        event: LifecycleEventKind,
    ) -> Callable[..., LifecycleHandler | Callable[[LifecycleHandler], LifecycleHandler]]:
        def decorator(
            handler: LifecycleHandler | LifecyclePriority | None = None,
            /,
            *,
            priority: LifecyclePriority = LifecyclePriority.DEFAULT,
        ) -> LifecycleHandler | Callable[[LifecycleHandler], LifecycleHandler]:
            if isinstance(handler, LifecyclePriority):
                priority = handler
                handler = None
            if handler is None:
                return lambda decorated_handler: self._register_and_return(event, decorated_handler, priority)
            self.register_lifecycle(event, handler, priority)
            return handler

        return decorator

    def _register_and_return(
        self,
        event: LifecycleEventKind,
        handler: LifecycleHandler,
        priority: LifecyclePriority,
    ) -> LifecycleHandler:
        self.register_lifecycle(event, handler, priority)
        return handler

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The lifecycle registry is frozen.")
