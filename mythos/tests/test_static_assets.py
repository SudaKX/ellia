import asyncio
import os

from _helpers.object_store import FakeObjectStore
from mythos.core.database import Database
from mythos.persistence.base import Base
from mythos.persistence.models.static_files import StaticFileRegistration
from mythos.registry.files import FileReference
from mythos.services.files.static_assets import StaticAssetPublisher
from mythos.services.object_store.service import Boto3ObjectStore


def test_static_assets_upload_on_first_seen_and_content_change(tmp_path) -> None:
    async def scenario() -> None:
        puzzle_root = tmp_path / "puzzles"
        source_path = puzzle_root / "intro" / "assets" / "README.txt"
        source_path.parent.mkdir(parents=True)
        source_path.write_text("first", encoding="utf-8")
        database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'assets.sqlite3').as_posix()}")
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        writer = FakeObjectStore()
        publisher = StaticAssetPublisher(database.session_factory, writer, puzzle_root)
        source = FileReference("intro", "assets/README.txt", "text/plain; charset=utf-8")

        first = await publisher.materialize((source,))
        reused = await publisher.materialize((source,))
        assert writer.upload_keys == ["static/intro/assets/README.txt"]
        assert reused == first

        source_stat = source_path.stat()
        source_path.write_text("second", encoding="utf-8")
        os.utime(source_path, ns=(source_stat.st_atime_ns, source_stat.st_mtime_ns))
        updated = await publisher.materialize((source,))
        assert writer.upload_keys == ["static/intro/assets/README.txt", "static/intro/assets/README.txt"]
        assert updated[source.source_locator].content_digest != first[source.source_locator].content_digest

        async with database.session_factory() as session:
            registration = await session.get(StaticFileRegistration, source.source_locator)
            assert registration is not None
            assert registration.object_key == "static/intro/assets/README.txt"
            assert registration.retired_at is None
        await database.dispose()

    asyncio.run(scenario())


def test_boto3_object_store_uploads_without_object_versions(tmp_path) -> None:
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
        client = FakeBotoClient({})
        store = Boto3ObjectStore(client, "mythos")
        reference = await store.put_bytes(source_path.read_bytes(), object_key="static/test/source.txt", media_type="text/plain")
        assert client.requests[0]["Bucket"] == "mythos"
        assert client.requests[0]["Key"] == "static/test/source.txt"

    asyncio.run(scenario())
