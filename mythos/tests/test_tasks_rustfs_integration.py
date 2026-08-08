from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

import boto3
import pytest
from botocore.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from mythos.core.file_ids import FileIdCodec
from mythos.core.player_interfaces import PlayerInterfaces
from mythos.persistence.base import Base
from mythos.persistence.models import PlayerArtifact, PlayerRecord, PlayerTaskState
from mythos.players.factory import PlayerFactory
from mythos.registry.artifacts import ArtifactTemplate, RawArtifact
from mythos.registry.artifacts import module_handler
from mythos.registry.bundle import RegistryBundle
from mythos.registry.progress import NormalProgressNode
from mythos.services.object_store.service import Boto3ObjectStore
from mythos.services.tasks import TaskExecutor

pytestmark = pytest.mark.skipif(
    os.getenv("MYTHOS_RUSTFS_INTEGRATION") != "1",
    reason="Set MYTHOS_RUSTFS_INTEGRATION=1 to run against a local RustFS instance.",
)


def test_task_handler_generates_artifact_in_rustfs(tmp_path: Path) -> None:
    endpoint = os.getenv("MYTHOS_RUSTFS_TEST_ENDPOINT", "http://127.0.0.1:9000")
    access_key = os.getenv("MYTHOS_RUSTFS_TEST_ACCESS_KEY", "rustfsadmin")
    secret_key = os.getenv("MYTHOS_RUSTFS_TEST_SECRET_KEY", "rustfsadmin")
    bucket = f"mythos-task-{uuid4().hex}"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        use_ssl=endpoint.startswith("https://"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    bucket_created = False

    try:
        client.create_bucket(Bucket=bucket)
        bucket_created = True

        @module_handler("test.tasks-rustfs")(1)
        async def artifact_generator(_player) -> RawArtifact:
            return RawArtifact(b"created by a task")

        async def scenario() -> None:
            registries = RegistryBundle()
            registries.progress.register(NormalProgressNode("start", (), is_entry=True))
            registries.artifacts.register_template(
                ArtifactTemplate("test.task-artifact", "text/plain", "task.txt", artifact_generator)
            )

            async def handler(context) -> None:
                await context.player.artifacts.generate_artifact("test.task-artifact", context.player)

            registries.tasks.register(
                "test.generate-artifact",
                handler,
                dependencies=PlayerInterfaces.ARTIFACTS,
            )
            file_ids = FileIdCodec("test-file-id-signing-key-with-at-least-32-bytes")
            catalogs = registries.freeze(file_ids)
            object_store = Boto3ObjectStore(client, bucket)
            player_id = uuid4()
            database_path = tmp_path / "task-rustfs.sqlite3"
            engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            session_factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
            async with session_factory() as session:
                session.add_all(
                    [
                        PlayerRecord(
                            id=player_id,
                            username="task-rustfs-player",
                            username_normalized="task-rustfs-player",
                        ),
                        PlayerTaskState(
                            player_id=player_id,
                            task_id="test.generate-artifact",
                            meta="{}",
                        ),
                    ]
                )
                await session.commit()
                executor = TaskExecutor(
                    PlayerFactory(catalogs, object_store, file_ids),
                    catalogs.tasks,
                )
                async with session.begin():
                    report = await executor.run_itx(session, player_id)

                artifact = await session.scalar(
                    select(PlayerArtifact).where(
                        PlayerArtifact.player_id == player_id,
                        PlayerArtifact.artifact_id == "test.task-artifact",
                    )
                )
                assert report.body()["tasks"][0]["status"] == "success"
                assert artifact is not None
                assert client.get_object(Bucket=bucket, Key=artifact.object_key)["Body"].read() == b"created by a task"
            await engine.dispose()

        asyncio.run(scenario())
    finally:
        if bucket_created:
            objects = client.list_objects_v2(Bucket=bucket).get("Contents", [])
            if objects:
                client.delete_objects(
                    Bucket=bucket,
                    Delete={"Objects": [{"Key": item["Key"]} for item in objects]},
                )
            client.delete_bucket(Bucket=bucket)
