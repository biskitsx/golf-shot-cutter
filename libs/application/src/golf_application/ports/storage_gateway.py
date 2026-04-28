from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class SignedUrl(BaseModel):
    url: str
    expires_at: datetime


class StorageGateway(Protocol):
    async def signed_put_url(self, key: str, *, content_type: str) -> SignedUrl: ...
    async def signed_get_url(self, key: str) -> SignedUrl: ...
    async def delete_object(self, key: str) -> None: ...
