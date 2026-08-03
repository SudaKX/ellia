from mythos.players.context import PlayerLifecycleContext
from mythos.registry.lifecycle.catalog import LifecycleCatalog


class PlayerLifecycleDispatcher:
    def __init__(self, catalog: LifecycleCatalog) -> None:
        self._catalog = catalog

    async def publish(self, context: PlayerLifecycleContext) -> None:
        for handler in self._catalog.listeners_for(context.event):
            await handler(context)
