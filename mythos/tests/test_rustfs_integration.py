import asyncio
import os
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

import boto3
import pytest
from botocore.config import Config

from mythos.services.object_store.service import Boto3ObjectStore


pytestmark = pytest.mark.skipif(
    os.getenv("MYTHOS_RUSTFS_INTEGRATION") != "1",
    reason="Set MYTHOS_RUSTFS_INTEGRATION=1 to run against a local RustFS instance.",
)


def test_rustfs_versions_and_presigned_reads(tmp_path: Path) -> None:
    endpoint = os.getenv("MYTHOS_RUSTFS_TEST_ENDPOINT", "http://127.0.0.1:9000")
    access_key = os.getenv("MYTHOS_RUSTFS_TEST_ACCESS_KEY", "rustfsadmin")
    secret_key = os.getenv("MYTHOS_RUSTFS_TEST_SECRET_KEY", "rustfsadmin")
    bucket = f"mythos-integration-{uuid4().hex}"
    object_key = "static/integration/versioned.txt"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        use_ssl=endpoint.startswith("https://"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    source_path = tmp_path / "versioned.txt"
    created_versions: list[str] = []

    try:
        client.create_bucket(Bucket=bucket)
        client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        assert client.get_bucket_versioning(Bucket=bucket).get("Status") == "Enabled"

        async def scenario() -> None:
            store = Boto3ObjectStore(client, bucket)
            source_path.write_text("first version", encoding="utf-8")
            first = await store.put_file(
                source_path,
                object_key=object_key,
                media_type="text/plain; charset=utf-8",
            )
            source_path.write_text("second version", encoding="utf-8")
            second = await store.put_file(
                source_path,
                object_key=object_key,
                media_type="text/plain; charset=utf-8",
            )
            created_versions.extend((first.version_id, second.version_id))
            assert first.version_id != second.version_id

            first_url = await store.presign_get(
                first,
                expires_in_seconds=60,
                content_disposition='inline; filename="versioned.txt"',
            )
            second_url = await store.presign_get(
                second,
                expires_in_seconds=60,
                content_disposition='inline; filename="versioned.txt"',
            )
            with urlopen(first_url.url, timeout=10) as response:
                assert response.read() == b"first version"
            with urlopen(second_url.url, timeout=10) as response:
                assert response.read() == b"second version"

        asyncio.run(scenario())
    finally:
        for version_id in created_versions:
            client.delete_object(Bucket=bucket, Key=object_key, VersionId=version_id)
        client.delete_bucket(Bucket=bucket)
