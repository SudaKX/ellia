from __future__ import annotations

from typing import Callable
from uuid import UUID

from cachetools import TTLCache

from mythos.endpoints.models import ActionExecutionResult

_MISSING = object()


class RequestInProgressError(Exception):
    pass


class RequestReplayForbiddenError(Exception):
    pass


class RequestCache:
    def __init__(
        self,
        *,
        maxsize: int,
        ttl_seconds: int,
        timer: Callable[[], float] | None = None,
    ) -> None:
        if timer is None:
            self._entries: TTLCache[UUID, ActionExecutionResult | None] = TTLCache(
                maxsize=maxsize,
                ttl=ttl_seconds,
            )
        else:
            self._entries = TTLCache(maxsize=maxsize, ttl=ttl_seconds, timer=timer)

    def reserve(self, request_id: UUID, player_id: UUID) -> ActionExecutionResult | None:
        entry = self._entries.get(request_id, _MISSING)
        if entry is _MISSING:
            self._entries[request_id] = None
            return None
        if entry is None:
            raise RequestInProgressError
        if entry.owner_player_id != player_id:
            raise RequestReplayForbiddenError
        return entry

    def complete(self, request_id: UUID, result: ActionExecutionResult) -> None:
        self._entries[request_id] = result

    def release(self, request_id: UUID) -> None:
        self._entries.pop(request_id, None)
