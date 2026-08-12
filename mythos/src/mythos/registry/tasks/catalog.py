from __future__ import annotations

from collections.abc import Mapping

from mythos.registry.errors import RegistryError
from mythos.registry.tasks.definitions import TaskDefinition
from mythos.registry.tasks.snapshot import TaskSnapshot


class TaskNotFoundError(RegistryError):
    pass


class TaskCatalog:
    def __init__(self, definitions: Mapping[str, TaskDefinition]) -> None:
        self._definitions = dict(definitions)
        self._snapshot = TaskSnapshot.from_ids(tuple(self._definitions))

    def task(self, task_id: str) -> TaskDefinition:
        try:
            return self._definitions[task_id]
        except KeyError as error:
            raise TaskNotFoundError(task_id) from error

    def task_or_none(self, task_id: str) -> TaskDefinition | None:
        return self._definitions.get(task_id)

    @property
    def task_ids(self) -> frozenset[str]:
        return frozenset(self._definitions)

    @property
    def handler_ids(self) -> frozenset[str]:
        return self.task_ids

    @property
    def registry_version(self) -> str:
        return self._snapshot.registry_version

    def snapshot(self) -> TaskSnapshot:
        return self._snapshot
