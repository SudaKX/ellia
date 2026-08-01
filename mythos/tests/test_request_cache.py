from uuid import uuid4

import pytest

from mythos.core.commands import CachedResponse, RequestCache, RequestInProgressError, RequestReplayForbiddenError, ResponseSpec


def _result(player_id):
    return CachedResponse(
        owner_player_id=player_id,
        response=ResponseSpec(
            status_code=200,
            body={"content": {"ok": True}, "followups": []},
            headers={},
        ),
    )


def test_request_cache_reserves_replays_and_expires() -> None:
    now = [0.0]
    cache = RequestCache(maxsize=4, ttl_seconds=10, timer=lambda: now[0])
    request_id = uuid4()
    owner = uuid4()

    assert cache.reserve(request_id, owner) is None
    with pytest.raises(RequestInProgressError):
        cache.reserve(request_id, owner)

    result = _result(owner)
    cache.complete(request_id, result)
    assert cache.reserve(request_id, owner) is result
    with pytest.raises(RequestReplayForbiddenError):
        cache.reserve(request_id, uuid4())

    now[0] = 11.0
    assert cache.reserve(request_id, owner) is None


def test_request_cache_releases_failed_reservations() -> None:
    cache = RequestCache(maxsize=4, ttl_seconds=10)
    request_id = uuid4()
    owner = uuid4()

    assert cache.reserve(request_id, owner) is None
    cache.release(request_id)
    assert cache.reserve(request_id, owner) is None
