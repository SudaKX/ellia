from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

EffectCallback = Callable[[], Awaitable[None]]


@dataclass(frozen=True)
class PendingEffect:
    kind: str
    _execute_callback: EffectCallback

    async def execute(self) -> None:
        await self._execute_callback()


@dataclass(frozen=True)
class SetCheckpointEffect(PendingEffect):
    checkpoint: str | None
