from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from mythos.registry.files.definitions import ObjectReference

if TYPE_CHECKING:
    from mythos.core.config import Settings


class ObjectStoreUnavailableError(Exception):
    pass


class ObjectStoreError(Exception):
    pass


@dataclass(frozen=True)
class PresignedObjectUrl:
    url: str
    expires_at: datetime


class ObjectStoreReader(Protocol):
    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
    ) -> PresignedObjectUrl: ...


class StaticObjectWriter(Protocol):
    async def put_file(
        self,
        source_path: Path,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference: ...


class ObjectStore(ObjectStoreReader, StaticObjectWriter, Protocol):
    pass


class UnconfiguredObjectStore:
    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
    ) -> PresignedObjectUrl:
        del reference, expires_in_seconds, content_disposition
        raise ObjectStoreUnavailableError("Object storage is not configured.")

    async def put_file(
        self,
        source_path: Path,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference:
        del source_path, object_key, media_type
        raise ObjectStoreUnavailableError("Object storage is not configured.")


class Boto3ObjectStore:
    def __init__(self, client: object, bucket: str) -> None:
        self._client = client
        self._bucket = bucket

    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
    ) -> PresignedObjectUrl:
        params: dict[str, str] = {
            "Bucket": self._bucket,
            "Key": reference.key,
            "ResponseContentType": reference.media_type,
            "ResponseContentDisposition": content_disposition,
        }
        params["VersionId"] = reference.version_id
        try:
            url = await asyncio.to_thread(
                self._client.generate_presigned_url,  # type: ignore[union-attr]
                "get_object",
                Params=params,
                ExpiresIn=expires_in_seconds,
            )
        except Exception as error:
            raise ObjectStoreError("Unable to issue an object download URL.") from error
        return PresignedObjectUrl(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in_seconds),
        )

    async def put_file(
        self,
        source_path: Path,
        *,
        object_key: str,
        media_type: str,
    ) -> ObjectReference:
        return await asyncio.to_thread(self._put_file_sync, source_path, object_key, media_type)

    def _put_file_sync(self, source_path: Path, object_key: str, media_type: str) -> ObjectReference:
        try:
            size_bytes = source_path.stat().st_size
            with source_path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
                source.seek(0)
                response = self._client.put_object(  # type: ignore[union-attr]
                    Bucket=self._bucket,
                    Key=object_key,
                    Body=source,
                    ContentType=media_type,
                )
        except Exception as error:
            raise ObjectStoreError("Unable to upload a static object.") from error
        version_id = response.get("VersionId") if isinstance(response, dict) else None
        if not isinstance(version_id, str) or not version_id:
            raise ObjectStoreError("Object storage did not return a version ID for the uploaded object.")
        return ObjectReference(
            key=object_key,
            content_digest=f"sha256:{digest}",
            media_type=media_type,
            size_bytes=size_bytes,
            version_id=version_id,
        )


def create_object_store(settings: Settings) -> ObjectStore:
    if not settings.object_store_configured:
        return UnconfiguredObjectStore()
    try:
        import boto3
        from botocore.config import Config
    except ImportError as error:
        raise RuntimeError("boto3 must be installed to use object storage.") from error
    client = boto3.client(
        "s3",
        endpoint_url=settings.object_store_endpoint,
        region_name=settings.object_store_region,
        aws_access_key_id=settings.object_store_access_key.get_secret_value(),
        aws_secret_access_key=settings.object_store_secret_key.get_secret_value(),
        use_ssl=settings.object_store_use_tls,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    assert settings.object_store_bucket is not None
    return Boto3ObjectStore(client, settings.object_store_bucket)
