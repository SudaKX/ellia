from __future__ import annotations

from collections.abc import Callable

from mythos.eventbus.catalog import EventCatalog, EventRegistration
from mythos.eventbus.definitions import Event, EventHandler, EventPriority
from mythos.registry.callbacks import callback_dependencies, validate_callback
from mythos.registry.errors import RegistryError, RegistryFrozenError


class EventRegistry:
    def __init__(self) -> None:
        self._registrations: dict[type[Event], list[EventRegistration]] = {}
        self._sequence = 0
        self._frozen = False
        self._catalog: EventCatalog | None = None

    def on(
        self,
        event_type: type[Event],
        *,
        priority: EventPriority = EventPriority.DEFAULT,
    ) -> Callable[[EventHandler], EventHandler]:
        self._ensure_mutable()
        if not isinstance(event_type, type) or not issubclass(event_type, Event):
            raise RegistryError("Event listeners require an Event type.")
        if not isinstance(priority, EventPriority):
            raise RegistryError("Event listeners require an EventPriority.")

        def register(handler: EventHandler) -> EventHandler:
            self.register(event_type, handler, priority=priority)
            return handler

        return register

    def register(
        self,
        event_type: type[Event],
        handler: EventHandler,
        *,
        priority: EventPriority = EventPriority.DEFAULT,
    ) -> None:
        self._ensure_mutable()
        if not isinstance(event_type, type) or not issubclass(event_type, Event):
            raise RegistryError("Event listeners require an Event type.")
        if not isinstance(priority, EventPriority):
            raise RegistryError("Event listeners require an EventPriority.")
        entries = self._registrations.setdefault(event_type, [])
        if any(registered_handler is handler for _priority, _sequence, registered_handler, _dependencies in entries):
            raise RegistryError("Event handlers may only be registered once per event type.")
        try:
            validate_callback(
                handler,
                field_name="Event listener",
                parameter_count=1,
                asynchronous=True,
                require_dependencies=True,
            )
            dependencies = callback_dependencies(
                handler,
                field_name="Event listener",
                required=True,
            )
        except ValueError as error:
            raise RegistryError("Invalid event listener.") from error
        if dependencies is None:
            raise RuntimeError("Validated event listeners must declare dependencies.")
        entries.append((priority, self._sequence, handler, dependencies))
        self._sequence += 1

    def freeze(self) -> EventCatalog:
        if self._catalog is None:
            self._catalog = EventCatalog(self._registrations)
            self._frozen = True
        return self._catalog

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The event registry is frozen.")
