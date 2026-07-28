import asyncio
import os
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import boto3
import httpx
import pytest
from botocore.config import Config
from pydantic import SecretStr

from mythos.core.config import Settings
from mythos.core.database import Database
from mythos.main import create_app
from mythos.persistence.base import Base


pytestmark = pytest.mark.skipif(
    os.getenv("MYTHOS_RUSTFS_INTEGRATION") != "1",
    reason="Set MYTHOS_RUSTFS_INTEGRATION=1 to run against a local RustFS instance.",
)


def test_example_module_publishes_and_reads_from_rustfs(tmp_path: Path) -> None:
    endpoint = os.getenv("MYTHOS_RUSTFS_TEST_ENDPOINT", "http://127.0.0.1:9000")
    access_key = os.getenv("MYTHOS_RUSTFS_TEST_ACCESS_KEY", "rustfsadmin")
    secret_key = os.getenv("MYTHOS_RUSTFS_TEST_SECRET_KEY", "rustfsadmin")
    bucket = f"mythos-example-{uuid4().hex}"
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
        client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})

        async def scenario() -> None:
            settings = Settings(
                environment="test",
                database_url=f"sqlite+aiosqlite:///{(tmp_path / 'example-rustfs.sqlite3').as_posix()}",
                checkpoint_directory=tmp_path / "checkpoints",
                jwt_signing_key=SecretStr("test-jwt-signing-key-with-at-least-32-bytes"),
                refresh_token_pepper=SecretStr("test-refresh-token-pepper-with-at-least-32-bytes"),
                file_id_signing_key=SecretStr("test-file-id-signing-key-with-at-least-32-bytes"),
                refresh_cookie_secure=False,
                object_store_endpoint=endpoint,
                object_store_bucket=bucket,
                object_store_access_key=SecretStr(access_key),
                object_store_secret_key=SecretStr(secret_key),
                object_store_use_tls=endpoint.startswith("https://"),
                puzzle_root=Path(__file__).resolve().parents[1] / "src" / "mythos" / "puzzles",
            )
            database = Database(settings.database_url)
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            await database.dispose()

            app = create_app(settings)
            async with app.router.lifespan_context(app):
                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    registration = await client.post(
                        "/api/v1/auth/register",
                        json={"username": "rustfs-example-player", "password": "correct-horse-battery"},
                    )
                    assert registration.status_code == 201
                    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

                    initial_tree = await client.get("/api/v1/files/tree", headers=headers)
                    readme = initial_tree.json()["directories"][0]["files"][0]
                    readme_url = await client.get(
                        f"/api/v1/files/{readme['file_id']}/{readme['content_token']}/content-url",
                        headers=headers,
                    )
                    assert b"ECHO-7" in await asyncio.to_thread(_read_url, readme_url.json()["url"])

                    completed = await client.post(
                        "/api/v1/validations/example-answer/attempts",
                        headers={**headers, "Request-ID": str(uuid4())},
                        json={"answer": "echo-7"},
                    )
                    assert completed.json() == {"content": {"accepted": True}, "followups": []}

                    completed_tree = await client.get("/api/v1/files/tree", headers=headers)
                    archive = next(
                        directory
                        for directory in completed_tree.json()["directories"]
                        if directory["path"] == "/archive"
                    )
                    result = archive["files"][0]
                    result_url = await client.get(
                        f"/api/v1/files/{result['file_id']}/{result['content_token']}/content-url",
                        headers=headers,
                    )
                    assert b"ARCHIVE UNLOCKED" in await asyncio.to_thread(_read_url, result_url.json()["url"])

        asyncio.run(scenario())
    finally:
        if bucket_created:
            _delete_bucket_versions(client, bucket)


def _read_url(url: str) -> bytes:
    with urlopen(url, timeout=10) as response:
        return response.read()


def _delete_bucket_versions(client, bucket: str) -> None:
    versions = client.list_object_versions(Bucket=bucket)
    objects = [
        {"Key": item["Key"], "VersionId": item["VersionId"]}
        for item in [*versions.get("Versions", []), *versions.get("DeleteMarkers", [])]
    ]
    if objects:
        client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
    client.delete_bucket(Bucket=bucket)
