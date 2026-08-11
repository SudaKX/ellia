from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mythos.registry.errors import RegistryError, RegistryFrozenError
from mythos.registry.lifecycle import (
    LifecycleEventKind,
    LifecyclePriority,
    LifecycleRegistry,
    PlayerConstructEvent,
    PlayerDeconstructEvent,
)


async def _default_handler(_context) -> None:
    pass


def test_lifecycle_events_expose_fixed_kinds() -> None:
    player_id = uuid4()
    occurred_at = datetime.now(UTC)

    construct = PlayerConstructEvent(player_id, occurred_at, "registration")
    deconstruct = PlayerDeconstructEvent(player_id, occurred_at, "deletion")

    assert LifecycleEventKind.CONSTRUCT == 1
    assert LifecycleEventKind.DECONSTRUCT == 2
    assert LifecyclePriority.EARLY == 100
    assert LifecyclePriority.DEFAULT == 200
    assert LifecyclePriority.LATE == 300
    assert construct.player_id is player_id
    assert construct.occurred_at is occurred_at
    assert construct.kind is LifecycleEventKind.CONSTRUCT
    assert deconstruct.kind is LifecycleEventKind.DECONSTRUCT


def test_lifecycle_catalog_orders_listeners_by_priority_then_registration_sequence() -> None:
    registry = LifecycleRegistry()

    async def default_first(_context) -> None:
        pass

    async def early(_context) -> None:
        pass

    async def default_second(_context) -> None:
        pass

    async def late(_context) -> None:
        pass

    registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, default_first)
    registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, early, LifecyclePriority.EARLY)
    registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, default_second)
    registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, late, LifecyclePriority.LATE)

    catalog = registry.freeze()
    event = PlayerConstructEvent(uuid4(), datetime.now(UTC), "first_login")

    assert catalog.listeners_for(LifecycleEventKind.CONSTRUCT) == (
        early,
        default_first,
        default_second,
        late,
    )
    assert catalog.listeners_for(event) == catalog.listeners_for(LifecycleEventKind.CONSTRUCT)
    assert isinstance(catalog.listeners_for(LifecycleEventKind.CONSTRUCT), tuple)
    assert catalog.listeners_for(LifecycleEventKind.DECONSTRUCT) == ()


def test_lifecycle_decorators_support_default_and_explicit_priorities() -> None:
    registry = LifecycleRegistry()

    @registry.on_construct
    async def construct_default(_context) -> None:
        pass

    @registry.on_construct(priority=LifecyclePriority.EARLY)
    async def construct_early(_context) -> None:
        pass

    @registry.on_deconstruct(LifecyclePriority.LATE)
    async def deconstruct_late(_context) -> None:
        pass

    catalog = registry.freeze()

    assert catalog.listeners_for(LifecycleEventKind.CONSTRUCT) == (construct_early, construct_default)
    assert catalog.listeners_for(LifecycleEventKind.DECONSTRUCT) == (deconstruct_late,)


def test_lifecycle_registry_rejects_duplicate_handler_object_per_event() -> None:
    registry = LifecycleRegistry()
    registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, _default_handler)

    with pytest.raises(RegistryError, match="only be registered once"):
        registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, _default_handler)

    registry.register_lifecycle(LifecycleEventKind.DECONSTRUCT, _default_handler)


def test_lifecycle_registry_rejects_registration_after_freeze() -> None:
    registry = LifecycleRegistry()
    catalog = registry.freeze()

    assert registry.freeze() is catalog
    with pytest.raises(RegistryFrozenError):
        registry.register_lifecycle(LifecycleEventKind.CONSTRUCT, _default_handler)
