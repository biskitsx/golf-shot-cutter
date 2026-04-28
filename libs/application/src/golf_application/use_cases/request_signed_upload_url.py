from pydantic import BaseModel

from golf_domain.ids import SessionId

from ..ports import SessionRepository, SignedUrl, StorageGateway


class RequestSignedUploadUrlInput(BaseModel):
    session_id: SessionId


class RequestSignedUploadUrlUseCase:
    def __init__(self, *, sessions: SessionRepository, storage: StorageGateway) -> None:
        self._sessions = sessions
        self._storage = storage

    async def execute(self, input: RequestSignedUploadUrlInput) -> SignedUrl:
        session = await self._sessions.get(input.session_id)
        return await self._storage.signed_put_url(session.raw_video_key, content_type="video/mp4")
