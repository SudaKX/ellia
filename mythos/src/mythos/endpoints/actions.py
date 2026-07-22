from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Mapping

from mythos.players.effects import PendingEffect
from mythos.players.plan import PendingEffectPlan

if TYPE_CHECKING:
    from mythos.endpoints.execution import ActionRuntime


class ActionExecutionError(Exception):
    pass


class ActionRejected(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class Action(ABC):
    @abstractmethod
    async def execute(self, runtime: ActionRuntime) -> None:
        raise NotImplementedError


@dataclass(frozen=True)
class EffectAction(Action):
    effects: tuple[PendingEffect, ...] = field(init=False)

    def __init__(self, plan: PendingEffectPlan) -> None:
        if type(plan) is not PendingEffectPlan:
            raise TypeError("EffectAction requires a framework PendingEffectPlan.")
        object.__setattr__(self, "effects", plan.freeze())

    async def execute(self, runtime: ActionRuntime) -> None:
        for effect in self.effects:
            await effect.execute()


@dataclass(frozen=True)
class ResponseAction(Action):
    body: Mapping[str, Any]
    status_code: int = 200
    headers: Mapping[str, str] = field(default_factory=dict)

    async def execute(self, runtime: ActionRuntime) -> None:
        runtime.response_builder.set_response(self.status_code, self.body, self.headers)


@dataclass(frozen=True)
class FollowupAction(Action):
    body: Mapping[str, Any]

    async def execute(self, runtime: ActionRuntime) -> None:
        runtime.response_builder.add_followup(self.body)


@dataclass(frozen=True)
class RejectAction(Action):
    status_code: int
    detail: str

    async def execute(self, runtime: ActionRuntime) -> None:
        raise ActionRejected(self.status_code, self.detail)


_FRAMEWORK_ACTION_TYPES = (EffectAction, ResponseAction, FollowupAction, RejectAction)


def is_framework_action(value: object) -> bool:
    return type(value) in _FRAMEWORK_ACTION_TYPES
