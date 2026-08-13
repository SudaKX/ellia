from __future__ import annotations

from collections.abc import Iterable, Mapping

from mythos.eventbus.definitions import Event, EventHandler, EventPriority
from mythos.players.interfaces import PlayerInterfaces


type EventRegistration = tuple[EventPriority, int, EventHandler, PlayerInterfaces]


class EventCatalog:
    def __init__(self, registrations: Mapping[type[Event], Iterable[EventRegistration]]) -> None:
        self._listeners_by_type: dict[type[Event], tuple[EventHandler, ...]] = {}
        self._dependencies_by_type: dict[type[Event], PlayerInterfaces] = {}
        for event_type, entries in registrations.items():
            ordered = tuple(sorted(entries, key=lambda entry: (entry[0], entry[1])))
            self._listeners_by_type[event_type] = tuple(entry[2] for entry in ordered)
            dependencies = PlayerInterfaces.NONE
            for _priority, _sequence, _handler, handler_dependencies in ordered:
                dependencies |= handler_dependencies
            self._dependencies_by_type[event_type] = dependencies

    def listeners_for(self, event: Event | type[Event]) -> tuple[EventHandler, ...]:
        event_type = type(event) if isinstance(event, Event) else event
        return self._listeners_by_type.get(event_type, ())

    def dependencies_for(self, event: Event | type[Event]) -> PlayerInterfaces:
        event_type = type(event) if isinstance(event, Event) else event
        return self._dependencies_by_type.get(event_type, PlayerInterfaces.NONE)
