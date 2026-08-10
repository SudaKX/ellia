from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeAlias

from mythos.players.interfaces import PlayerInterfaces

if TYPE_CHECKING:
    from mythos.players.context import TaskContext


TaskHandler: TypeAlias = Callable[["TaskContext"], Awaitable[None]]


class TaskHandlerError(Exception):
    """A recoverable task failure whose savepoint can be rolled back."""


@dataclass(frozen=True, slots=True)
class TaskDefinition:
    task_id: str
    handler: TaskHandler
    dependencies: PlayerInterfaces

    @property
    def handler_id(self) -> str:
        return self.task_id

    @staticmethod
    def validate_handler(handler: TaskHandler) -> None:
        if not inspect.iscoroutinefunction(handler):
            raise ValueError("Task handlers must be asynchronous.")
        try:
            parameters = tuple(inspect.signature(handler).parameters.values())
        except (TypeError, ValueError) as error:
            raise ValueError("Task handlers must have an inspectable signature.") from error
        positional_kinds = {
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        }
        if len(parameters) != 1 or parameters[0].kind not in positional_kinds:
            raise ValueError("Task handlers must accept exactly one positional parameter.")
