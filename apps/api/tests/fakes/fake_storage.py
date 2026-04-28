from datetime import datetime, timedelta

from app.infrastructure.storage.r2_storage import SignedUrl


class FakeStorage:
    def __init__(self, *, base: str = "https://fake-r2.local") -> None:
        self._base = base
        self.deleted: list[str] = []

    async def signed_put_url(self, key: str, *, content_type: str) -> SignedUrl:
        return SignedUrl(
            url=f"{self._base}/PUT/{key}?ct={content_type}",
            expires_at=datetime.now() + timedelta(minutes=15),
        )

    async def signed_get_url(self, key: str) -> SignedUrl:
        return SignedUrl(
            url=f"{self._base}/GET/{key}",
            expires_at=datetime.now() + timedelta(minutes=15),
        )

    async def delete_object(self, key: str) -> None:
        self.deleted.append(key)
