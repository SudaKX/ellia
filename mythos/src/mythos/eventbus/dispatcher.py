from mythos.eventbus.catalog import EventCatalog
from mythos.eventbus.definitions import Event, EventContext, PlayerEvent
from mythos.players.interfaces import PlayerInterfaces


class EventDispatchError(ValueError):
    pass


class EventDispatcher:
    def __init__(self, catalog: EventCatalog) -> None:
        self._catalog = catalog

    def dependencies_for(self, event: Event | type[Event]) -> PlayerInterfaces:
        return self._catalog.dependencies_for(event)

    async def publish(self, context: EventContext) -> None:
        if isinstance(context.event, PlayerEvent) and (
            context.player is None or context.player.id != context.event.player_id
        ):
            raise EventDispatchError("Event player does not match the dispatch context player.")
        for handler in self._catalog.listeners_for(context.event):
            await handler(context)
