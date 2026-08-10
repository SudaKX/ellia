from __future__ import annotations

import re
from collections.abc import Callable

from mythos.players.interfaces import PlayerInterfaces
from mythos.registry.errors import DuplicateStableIdError, RegistryError, RegistryFrozenError
from mythos.registry.tasks.catalog import TaskCatalog
from mythos.registry.tasks.definitions import TaskDefinition, TaskHandler

_TASK_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class TaskRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, TaskDefinition] = {}
        self._frozen = False
        self._catalog: TaskCatalog | None = None

    def task(
        self,
        task_id: str,
        *,
        dependencies: PlayerInterfaces = PlayerInterfaces.NONE,
    ) -> Callable[[TaskHandler], TaskHandler]:
        self._validate_task_id(task_id)
        self._validate_dependencies(dependencies)

        def decorate(handler: TaskHandler) -> TaskHandler:
            self.register(task_id, handler, dependencies=dependencies)
            return handler

        return decorate

    def register(
        self,
        task_id: str,
        handler: TaskHandler,
        *,
        dependencies: PlayerInterfaces = PlayerInterfaces.NONE,
    ) -> None:
        self._ensure_mutable()
        self._validate_task_id(task_id)
        self._validate_dependencies(dependencies)
        if task_id in self._definitions:
            raise DuplicateStableIdError(task_id)
        try:
            TaskDefinition.validate_handler(handler)
        except ValueError as error:
            raise RegistryError(f"Invalid task handler for {task_id!r}.") from error
        self._definitions[task_id] = TaskDefinition(task_id, handler, dependencies)

    def freeze(self) -> TaskCatalog:
        if self._catalog is not None:
            return self._catalog
        self._frozen = True
        self._catalog = TaskCatalog(self._definitions)
        return self._catalog

    @staticmethod
    def _validate_task_id(task_id: str) -> None:
        if not isinstance(task_id, str) or not _TASK_ID_PATTERN.fullmatch(task_id):
            raise RegistryError("Task IDs must be lowercase slugs up to 128 characters.")

    @staticmethod
    def _validate_dependencies(dependencies: PlayerInterfaces) -> None:
        if not isinstance(dependencies, PlayerInterfaces):
            raise RegistryError("Task dependencies require a PlayerInterfaces bitmask.")
        if int(dependencies) & ~int(PlayerInterfaces.ALL):
            raise RegistryError("Task dependencies contain unknown interface bits.")

    def _ensure_mutable(self) -> None:
        if self._frozen or self._catalog is not None:
            raise RegistryFrozenError("The task registry is frozen.")
