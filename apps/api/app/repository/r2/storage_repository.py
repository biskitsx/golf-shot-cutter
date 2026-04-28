import asyncio
from datetime import UTC, datetime, timedelta

import boto3
from botocore.config import Config
from pydantic import BaseModel


class SignedUrl(BaseModel):
    url: str
    expires_at: datetime


class R2StorageRepository:
    def __init__(
        self,
        *,
        endpoint: str | None,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        ttl_seconds: int,
    ) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )
        self._bucket = bucket
        self._ttl = ttl_seconds

    async def signed_put_url(self, key: str, *, content_type: str) -> SignedUrl:
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=self._ttl,
        )
        return SignedUrl(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
        )

    async def signed_get_url(self, key: str) -> SignedUrl:
        url = await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=self._ttl,
        )
        return SignedUrl(
            url=url,
            expires_at=datetime.now(UTC) + timedelta(seconds=self._ttl),
        )

    async def delete_object(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)
