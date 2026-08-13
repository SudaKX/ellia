from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class Followup:
    action: str
    data: dict[str, Any]

    def to_json(self) -> dict[str, Any]:
        return {"action": self.action, "data": self.data}


class FollowupSink(Protocol):
    def add(self, followup: Followup) -> None: ...

    def checkpoint(self) -> None: ...

    def rollback(self) -> None: ...

    def to_json(self) -> list[dict[str, Any]]: ...


class FollowupCollector:
    def __init__(self) -> None:
        self._items: list[Followup] = []
        self._checkpoints: list[int] = []

    def add(self, followup: Followup) -> None:
        self._items.append(followup)

    def checkpoint(self) -> None:
        self._checkpoints.append(len(self._items))

    def rollback(self) -> None:
        if not self._checkpoints:
            raise RuntimeError("No Followup checkpoint is available for rollback.")
        del self._items[self._checkpoints.pop():]

    def to_json(self) -> list[dict[str, Any]]:
        return [followup.to_json() for followup in self._items]


class NullFollowupSink:
    def __init__(self) -> None:
        self._checkpoints: list[int] = []

    def add(self, followup: Followup) -> None:
        del followup

    def checkpoint(self) -> None:
        self._checkpoints.append(0)

    def rollback(self) -> None:
        if not self._checkpoints:
            raise RuntimeError("No Followup checkpoint is available for rollback.")
        self._checkpoints.pop()

    def to_json(self) -> list[dict[str, Any]]:
        return []


@dataclass(frozen=True, slots=True)
class ContextScope:
    followup_sink: FollowupSink

    @classmethod
    def http(cls) -> ContextScope:
        return cls(FollowupCollector())

    @classmethod
    def silent(cls) -> ContextScope:
        return cls(NullFollowupSink())

    def follow(self, followup: Followup) -> None:
        self.followup_sink.add(followup)

    def followup_checkpoint(self) -> None:
        self.followup_sink.checkpoint()

    def followup_rollback(self) -> None:
        self.followup_sink.rollback()

    def to_json(self) -> list[dict[str, Any]]:
        return self.followup_sink.to_json()
