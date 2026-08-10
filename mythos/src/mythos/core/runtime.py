from __future__ import annotations

from dataclasses import dataclass

from mythos.commands.executor import EndpointCommandExecutor
from mythos.commands.pipeline import PipelinedTransaction
from mythos.commands.executor import TaskCommandExecutor
from mythos.players.loader import PlayerLoader
from mythos.registry.bundle import RuntimeCatalogs
from mythos.services.container import ServiceContainer
from mythos.services.lifecycle import PlayerLifecycleDispatcher
from mythos.services.object_store.service import ObjectStore


@dataclass(frozen=True)
class ApplicationRuntime:
    catalogs: RuntimeCatalogs
    player_loader: PlayerLoader
    services: ServiceContainer
    object_store: ObjectStore
    endpoint_executor: EndpointCommandExecutor
    task_command_executor: TaskCommandExecutor
    pipelined_transaction: PipelinedTransaction
    lifecycle_dispatcher: PlayerLifecycleDispatcher
