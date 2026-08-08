from __future__ import annotations

from typing import Callable
from uuid import UUID

from cachetools import TTLCache

from mythos.core.commands.models import CachedResponse

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
            self._entries: TTLCache[UUID, CachedResponse | None] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        else:
            self._entries = TTLCache(maxsize=maxsize, ttl=ttl_seconds, timer=timer)
        self._in_progress: set[UUID] = set()

    def reserve(self, request_id: UUID, player_id: UUID) -> CachedResponse | None:
        entry = self._entries.get(request_id, _MISSING)
        if entry is not _MISSING:
            if entry is None:
                raise RequestInProgressError
            if entry.owner_player_id != player_id:
                raise RequestReplayForbiddenError
            return entry
        if request_id in self._in_progress:
            raise RequestInProgressError
        self._in_progress.add(request_id)
        return None

    def complete(self, request_id: UUID, response: CachedResponse) -> None:
        self._in_progress.discard(request_id)
        self._entries[request_id] = response

    def release(self, request_id: UUID) -> None:
        self._in_progress.discard(request_id)
        self._entries.pop(request_id, None)
