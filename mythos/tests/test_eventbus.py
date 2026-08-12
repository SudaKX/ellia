from datetime import UTC, datetime
from uuid import uuid4

import pytest

from mythos.core.followups import ContextScope
from mythos.eventbus import (
    EventContext,
    EventDispatchError,
    EventDispatcher,
    EventPriority,
    EventRegistry,
    PlayerConstructedEvent,
    PlayerDeconstructingEvent,
    VirtualAccountLoggedInEvent,
)
from mythos.players.interfaces import PlayerInterfaces
from mythos.players.player import Player
from mythos.registry.callbacks import module_handler
from mythos.registry.errors import RegistryError, RegistryFrozenError


def test_registry_validates_callbacks_freezes_and_orders_listeners() -> None:
    registry = EventRegistry()

    @registry.on(PlayerConstructedEvent)
    @module_handler("test.eventbus")(1, dependencies=PlayerInterfaces.PROGRESS)
    async def default_first(_context: EventContext) -> None:
        pass

    @registry.on(PlayerConstructedEvent, priority=EventPriority.EARLY)
    @module_handler("test.eventbus")(2, dependencies=PlayerInterfaces.CREDITS)
    async def early(_context: EventContext) -> None:
        pass

    @registry.on(PlayerConstructedEvent)
    @module_handler("test.eventbus")(3, dependencies=PlayerInterfaces.TASKS)
    async def default_second(_context: EventContext) -> None:
        pass

    catalog = registry.freeze()
    assert catalog.listeners_for(PlayerConstructedEvent) == (early, default_first, default_second)
    assert catalog.dependencies_for(PlayerConstructedEvent) == (
        PlayerInterfaces.PROGRESS | PlayerInterfaces.CREDITS | PlayerInterfaces.TASKS
    )
    assert registry.freeze() is catalog
    with pytest.raises(RegistryFrozenError):
        registry.on(PlayerConstructedEvent)


def test_builtin_player_events_are_immutable_typed_data() -> None:
    player_id = uuid4()
    occurred_at = datetime.now(UTC)
    construct = PlayerConstructedEvent(player_id=player_id, occurred_at=occurred_at, trigger="registration")
    deconstruct = PlayerDeconstructingEvent(player_id=player_id, occurred_at=occurred_at, trigger="deletion")
    login = VirtualAccountLoggedInEvent(
        player_id=player_id,
        occurred_at=occurred_at,
        account_id="test.account",
    )

    assert construct.player_id is deconstruct.player_id is login.player_id is player_id
    assert construct.occurred_at is deconstruct.occurred_at is login.occurred_at is occurred_at
    assert construct.trigger == "registration"
    assert deconstruct.trigger == "deletion"
    assert login.account_id == "test.account"


def test_registry_rejects_invalid_or_duplicate_listeners() -> None:
    registry = EventRegistry()

    async def undecorated(_context: EventContext) -> None:
        pass

    def synchronous(_context: EventContext) -> None:
        pass

    @module_handler("test.eventbus")(4, dependencies=PlayerInterfaces.NONE)
    async def valid(_context: EventContext) -> None:
        pass

    with pytest.raises(RegistryError, match="Invalid event listener"):
        registry.register(PlayerConstructedEvent, undecorated)
    with pytest.raises(RegistryError, match="Invalid event listener"):
        registry.register(PlayerConstructedEvent, synchronous)  # type: ignore[arg-type]
    registry.register(PlayerConstructedEvent, valid)
    with pytest.raises(RegistryError, match="only be registered once"):
        registry.register(PlayerConstructedEvent, valid)
    with pytest.raises(RegistryError, match="Event type"):
        registry.on(str)  # type: ignore[arg-type]


@pytest.mark.anyio
async def test_dispatcher_matches_exact_types_and_propagates_failures() -> None:
    registry = EventRegistry()
    calls: list[str] = []

    @registry.on(PlayerConstructedEvent)
    @module_handler("test.eventbus")(5, dependencies=PlayerInterfaces.NONE)
    async def first(_context: EventContext) -> None:
        calls.append("first")
        raise RuntimeError("stop")

    @registry.on(PlayerConstructedEvent)
    @module_handler("test.eventbus")(6, dependencies=PlayerInterfaces.NONE)
    async def second(_context: EventContext) -> None:
        calls.append("second")

    dispatcher = EventDispatcher(registry.freeze())
    player_id = uuid4()
    player = Player(player_id, None, None, writable=True)  # type: ignore[arg-type]
    scope = ContextScope.silent()
    with pytest.raises(RuntimeError, match="stop"):
        await dispatcher.publish(
            EventContext(
                player=player,
                event=PlayerConstructedEvent(player_id=player_id, occurred_at=datetime.now(UTC), trigger="registration"),
                scope=scope,
            )
        )
    assert calls == ["first"]

    await dispatcher.publish(
        EventContext(
            player=player,
            event=VirtualAccountLoggedInEvent(
                player_id=player_id,
                occurred_at=datetime.now(UTC),
                account_id="test.account",
            ),
            scope=scope,
        )
    )
    with pytest.raises(EventDispatchError):
        await dispatcher.publish(
            EventContext(
                player=player,
                event=PlayerConstructedEvent(
                    player_id=uuid4(),
                    occurred_at=datetime.now(UTC),
                    trigger="registration",
                ),
                scope=scope,
            )
        )
