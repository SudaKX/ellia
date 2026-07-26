import asyncio
import hashlib
import os

import pytest

from mythos.core.database import Database
from mythos.persistence.base import Base
from mythos.persistence.models.static_files import StaticFileRegistration
from mythos.registry.files import FileReference, ObjectReference
from mythos.services.files.static_assets import StaticAssetPublisher
from mythos.services.object_store.service import Boto3ObjectStore, ObjectStoreError


class FakeStaticObjectWriter:
    def __init__(self) -> None:
        self.uploads: list[str] = []

    async def put_file(self, source_path, *, object_key: str, media_type: str) -> ObjectReference:
        content = source_path.read_bytes()
        self.uploads.append(object_key)
        return ObjectReference(
            key=object_key,
            content_digest=f"sha256:{hashlib.sha256(content).hexdigest()}",
            media_type=media_type,
            size_bytes=len(content),
            version_id=f"version-{len(self.uploads)}",
        )


def test_static_assets_upload_on_first_seen_and_mtime_change(tmp_path) -> None:
    async def scenario() -> None:
        puzzle_root = tmp_path / "puzzles"
        source_path = puzzle_root / "intro" / "assets" / "README.txt"
        source_path.parent.mkdir(parents=True)
        source_path.write_text("first", encoding="utf-8")
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'assets.sqlite3').as_posix()}")
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        writer = FakeStaticObjectWriter()
        publisher = StaticAssetPublisher(database.session_factory, writer, puzzle_root)
        source = FileReference("intro", "assets/README.txt", "text/plain; charset=utf-8")

        first = await publisher.materialize((source,))
        reused = await publisher.materialize((source,))
        assert writer.uploads == ["static/intro/assets/README.txt"]
        assert first[source.source_locator].version_id == "version-1"
        assert reused == first

        source_path.write_text("second", encoding="utf-8")
        source_stat = source_path.stat()
        os.utime(source_path, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns + 1_000_000_000))
        updated = await publisher.materialize((source,))
        assert writer.uploads == ["static/intro/assets/README.txt", "static/intro/assets/README.txt"]
        assert updated[source.source_locator].version_id == "version-2"
        assert updated[source.source_locator].content_digest != first[source.source_locator].content_digest

        async with database.session_factory() as session:
            registration = await session.get(StaticFileRegistration, source.source_locator)
            assert registration is not None
            assert registration.object_key == "static/intro/assets/README.txt"
            assert registration.object_version_id == "version-2"
            assert registration.retired_at is None
        await database.dispose()

    asyncio.run(scenario())


def test_boto3_object_store_requires_version_id_for_static_upload(tmp_path) -> None:
    class FakeBotoClient:
        def __init__(self, response) -> None:
            self.response = response
            self.requests = []

        def put_object(self, **kwargs):
            self.requests.append(kwargs)
            return self.response

    async def scenario() -> None:
        source_path = tmp_path / "source.txt"
        source_path.write_text("content", encoding="utf-8")
        client = FakeBotoClient({"VersionId": "version-1"})
        store = Boto3ObjectStore(client, "mythos")
        reference = await store.put_file(source_path, object_key="static/test/source.txt", media_type="text/plain")
        assert reference.version_id == "version-1"
        assert client.requests[0]["Bucket"] == "mythos"
        assert client.requests[0]["Key"] == "static/test/source.txt"

        missing_version_store = Boto3ObjectStore(FakeBotoClient({}), "mythos")
        with pytest.raises(ObjectStoreError, match="version ID"):
            await missing_version_store.put_file(
                source_path,
                object_key="static/test/source.txt",
                media_type="text/plain",
            )

    asyncio.run(scenario())
