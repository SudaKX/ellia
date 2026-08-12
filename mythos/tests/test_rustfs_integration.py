import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
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


def test_rustfs_fixed_key_overwrite_and_presigned_reads(tmp_path: Path) -> None:
    endpoint = os.getenv("MYTHOS_RUSTFS_TEST_ENDPOINT", "http://127.0.0.1:9000")
    access_key = os.getenv("MYTHOS_RUSTFS_TEST_ACCESS_KEY", "rustfsadmin")
    secret_key = os.getenv("MYTHOS_RUSTFS_TEST_SECRET_KEY", "rustfsadmin")
    presign_ttl_seconds = int(os.getenv("MYTHOS_RUSTFS_TEST_PRESIGN_TTL", "60"))
    bucket = f"mythos-integration-{uuid4().hex}"
    object_key = "static/integration/overwrite.txt"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="us-east-1",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        use_ssl=endpoint.startswith("https://"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    source_path = tmp_path / "overwrite.txt"
    try:
        client.create_bucket(Bucket=bucket)

        async def scenario() -> None:
            store = Boto3ObjectStore(client, bucket)
            source_path.write_text("first version", encoding="utf-8")
            first = await store.put_bytes(
                source_path.read_bytes(),
                object_key=object_key,
                media_type="text/plain; charset=utf-8",
            )
            source_path.write_text("second version", encoding="utf-8")
            second = await store.put_bytes(
                source_path.read_bytes(),
                object_key=object_key,
                media_type="text/plain; charset=utf-8",
            )
            assert first.key == second.key == object_key
            assert first.content_digest != second.content_digest
            response_expires_at = datetime.now(UTC) + timedelta(seconds=presign_ttl_seconds)

            current_url = await store.presign_get(
                second,
                expires_in_seconds=presign_ttl_seconds,
                content_disposition='inline; filename="overwrite.txt"',
                response_cache_control="private, must-revalidate",
                response_expires_at=response_expires_at,
            )
            assert parse_qs(urlparse(current_url.url).query)["X-Amz-Expires"] == [str(presign_ttl_seconds)]
            with urlopen(current_url.url, timeout=10) as response:
                assert response.headers["Cache-Control"] == "private, must-revalidate"
                assert response.headers["Expires"]
                assert response.read() == b"second version"

        asyncio.run(scenario())
    finally:
        client.delete_object(Bucket=bucket, Key=object_key)
        client.delete_bucket(Bucket=bucket)
