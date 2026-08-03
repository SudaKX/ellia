from __future__ import annotations

from collections.abc import Iterable, Mapping

from mythos.registry.lifecycle.definitions import (
    LifecycleEventKind,
    LifecycleHandler,
    LifecyclePriority,
    PlayerLifecycleEvent,
)

type LifecycleRegistration = tuple[LifecyclePriority, int, LifecycleHandler]


class LifecycleCatalog:
    def __init__(self, registrations: Mapping[LifecycleEventKind, Iterable[LifecycleRegistration]]) -> None:
        listeners: list[tuple[LifecycleHandler, ...]] = [() for _ in range(max(LifecycleEventKind) + 1)]
        for event in LifecycleEventKind:
            listeners[int(event)] = tuple(
                handler
                for _priority, _sequence, handler in sorted(
                    registrations.get(event, ()),
                    key=lambda registration: (registration[0], registration[1]),
                )
            )
        self._listeners_by_event_id = tuple(listeners)

    def listeners_for(self, event: LifecycleEventKind | PlayerLifecycleEvent) -> tuple[LifecycleHandler, ...]:
        event_id = int(event.kind) if isinstance(event, PlayerLifecycleEvent) else int(event)
        return self._listeners_by_event_id[event_id]
