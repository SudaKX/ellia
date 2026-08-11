from __future__ import annotations

from typing import Callable
from uuid import UUID

from cachetools import TTLCache

from mythos.commands.models import CachedResponse

_MISSING = object()


class RequestInProgressError(Exception):
    pass


class RequestReplayForbiddenError(Exception):
    pass


class RequestLease:
    def __init__(self, cache: RequestCache, request_id: UUID, player_id: UUID) -> None:
        self._cache = cache
        self._request_id = request_id
        self.replay = cache.reserve(request_id, player_id)
        self._completed = self.replay is not None

    def complete(self, response: CachedResponse) -> None:
        if self.replay is not None:
            raise RuntimeError("A replayed request cannot be completed again.")
        if self._completed:
            raise RuntimeError("Request lease has already been completed.")
        self._cache.complete(self._request_id, response)
        self._completed = True

    def __enter__(self) -> RequestLease:
        return self

    def __exit__(self, _exception_type, _exception, _traceback) -> None:
        if self.replay is None and not self._completed:
            self._cache.release(self._request_id)


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

    def lease(self, request_id: UUID, player_id: UUID) -> RequestLease:
        return RequestLease(self, request_id, player_id)

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
