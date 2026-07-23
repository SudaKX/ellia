from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from mythos.core.config import Settings
    from mythos.registry.files.definitions import ObjectReference


class ObjectStoreUnavailableError(Exception):
    pass


class ObjectStoreError(Exception):
    pass


@dataclass(frozen=True)
class PresignedObjectUrl:
    url: str
    expires_at: datetime


class ObjectStore(Protocol):
    async def presign_get(
        self,
        reference: ObjectReference,
        *,
        expires_in_seconds: int,
        content_disposition: str,
    ) -> PresignedObjectUrl: ...


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
        if reference.version_id is not None:
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
