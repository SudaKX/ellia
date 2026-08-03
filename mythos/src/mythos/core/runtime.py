from __future__ import annotations

from dataclasses import dataclass

from mythos.core.commands.executor import CommandTransactionExecutor
from mythos.players.factory import PlayerFactory
from mythos.registry.bundle import RuntimeCatalogs
from mythos.services.container import ServiceContainer
from mythos.services.lifecycle import PlayerLifecycleDispatcher
from mythos.services.object_store.service import ObjectStore


@dataclass(frozen=True)
class ApplicationRuntime:
    catalogs: RuntimeCatalogs
    player_factory: PlayerFactory
    services: ServiceContainer
    object_store: ObjectStore
    command_executor: CommandTransactionExecutor
    lifecycle_dispatcher: PlayerLifecycleDispatcher
