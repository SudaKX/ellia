from __future__ import annotations

from dataclasses import dataclass

from mythos.commands.executor import AchievementCommandExecutor, EndpointCommandExecutor
from mythos.commands.pipeline import PipelinedTransaction
from mythos.commands.executor import TaskCommandExecutor
from mythos.eventbus import EventDispatcher
from mythos.players.loader import PlayerLoader
from mythos.registry.bundle import RuntimeCatalogs
from mythos.services.container import ServiceContainer
from mythos.services.object_store.service import ObjectStore


@dataclass(frozen=True)
class ApplicationRuntime:
    catalogs: RuntimeCatalogs
    player_loader: PlayerLoader
    services: ServiceContainer
    object_store: ObjectStore
    endpoint_executor: EndpointCommandExecutor
    achievement_command_executor: AchievementCommandExecutor
    task_command_executor: TaskCommandExecutor
    pipelined_transaction: PipelinedTransaction
    event_dispatcher: EventDispatcher
