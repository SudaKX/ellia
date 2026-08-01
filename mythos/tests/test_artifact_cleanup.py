from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from _helpers.object_store import FakeObjectStore
from mythos.persistence.base import Base
from mythos.persistence.models.artifacts import PlayerArtifact
from mythos.services.artifacts.cleanup import ArtifactCleanupService

pytestmark = pytest.mark.anyio


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


async def _put_bytes(store: FakeObjectStore, key: str, data: bytes) -> None:
    await store.put_bytes(data, object_key=key, media_type="application/octet-stream")


async def test_cleanup_deletes_only_unreferenced_artifacts(session) -> None:
    store = FakeObjectStore()
    service = ArtifactCleanupService(store)

    player_id = uuid4()
    referenced_key = "artifacts/player-1/artifact-a/1/digest-a"
    orphan_key = "artifacts/player-1/artifact-a/1/digest-old"
    other_prefix = "static/other-key"

    await _put_bytes(store, referenced_key, b"content")
    await _put_bytes(store, orphan_key, b"old content")
    await _put_bytes(store, other_prefix, b"static")

    session.add(
        PlayerArtifact(
            player_id=player_id,
            artifact_id="artifact-a",
            revision="1",
            object_key=referenced_key,
            object_version_id="version-1",
            content_digest="sha256:" + "a" * 64,
            media_type="text/plain",
            size_bytes=7,
            download_name="a.txt",
            meta={},
        )
    )
    await session.commit()

    result = await service.sweep(session)
    assert result == {"listed": 2, "referenced": 1, "deleted": 1, "skipped": 1}
    assert referenced_key in store.objects
    assert orphan_key not in store.objects
    assert other_prefix in store.objects


async def test_cleanup_keeps_no_objects_when_all_referenced(session) -> None:
    store = FakeObjectStore()
    service = ArtifactCleanupService(store)

    player_id = uuid4()
    key = "artifacts/player-2/artifact-b/1/digest"
    await _put_bytes(store, key, b"content")

    session.add(
        PlayerArtifact(
            player_id=player_id,
            artifact_id="artifact-b",
            revision="1",
            object_key=key,
            object_version_id="version-1",
            content_digest="sha256:" + "b" * 64,
            media_type="text/plain",
            size_bytes=7,
            download_name="b.txt",
            meta={},
        )
    )
    await session.commit()

    result = await service.sweep(session)
    assert result == {"listed": 1, "referenced": 1, "deleted": 0, "skipped": 1}
    assert key in store.objects


async def test_cleanup_deletes_all_artifacts_when_no_references(session) -> None:
    store = FakeObjectStore()
    service = ArtifactCleanupService(store)

    key = "artifacts/player-3/artifact-c/1/digest"
    await _put_bytes(store, key, b"content")

    result = await service.sweep(session)
    assert result == {"listed": 1, "referenced": 0, "deleted": 1, "skipped": 0}
    assert key not in store.objects


async def test_cleanup_counts_are_query_driven(session) -> None:
    store = FakeObjectStore()
    service = ArtifactCleanupService(store)

    referenced = "artifacts/player-4/artifact-d/1/digest"
    await _put_bytes(store, referenced, b"content")
    await _put_bytes(store, "artifacts/player-4/artifact-d/1/old-digest", b"old")

    session.add(
        PlayerArtifact(
            player_id=uuid4(),
            artifact_id="artifact-d",
            revision="1",
            object_key=referenced,
            object_version_id="version-1",
            content_digest="sha256:" + "d" * 64,
            media_type="text/plain",
            size_bytes=7,
            download_name="d.txt",
            meta={},
        )
    )
    await session.commit()

    result = await service.sweep(session)
    assert result["listed"] == 2
    assert result["referenced"] == 1
    assert result["deleted"] == 1
    assert result["skipped"] == 1

    # Only the referenced object remains.
    rows = await session.execute(select(PlayerArtifact.object_key))
    assert rows.scalars().all() == [referenced]
    assert store.objects == {referenced: b"content"}
