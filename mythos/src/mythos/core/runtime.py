from __future__ import annotations

from dataclasses import dataclass

from mythos.endpoints.dispatcher import EndpointDispatcher
from mythos.players.factory import PlayerFactory
from mythos.registry.bundle import RuntimeCatalogs
from mythos.services.container import ServiceContainer


@dataclass(frozen=True)
class ApplicationRuntime:
    catalogs: RuntimeCatalogs
    player_factory: PlayerFactory
    services: ServiceContainer
    endpoint_dispatcher: EndpointDispatcher
