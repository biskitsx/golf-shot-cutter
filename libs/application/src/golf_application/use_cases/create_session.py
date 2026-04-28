from datetime import datetime

from pydantic import BaseModel, Field

from golf_domain.ids import UserId
from golf_domain.session import Session, SessionStatus

from ..ports import Clock, IdGenerator, SessionRepository, StorageGateway


class CreateSessionInput(BaseModel):
    user_id: UserId | None
    original_filename: str = Field(min_length=1)
    pre_roll_seconds: float = Field(ge=0, default=2.0)
    post_roll_seconds: float = Field(ge=0, default=5.0)


class CreateSessionOutput(BaseModel):
    session_id: str
    signed_upload_url: str
    expires_at: datetime


class CreateSessionUseCase:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        storage: StorageGateway,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._storage = storage
        self._clock = clock
        self._ids = ids

    async def execute(self, input: CreateSessionInput) -> CreateSessionOutput:
        session_id = self._ids.session_id()
        raw_key = f"raw/{session_id}/{input.original_filename}"
        now = self._clock.now()
        signed = await self._storage.signed_put_url(raw_key, content_type="video/mp4")

        session = Session(
            id=session_id,  # type: ignore[arg-type]
            user_id=input.user_id,
            raw_video_key=raw_key,
            status=SessionStatus.UPLOADING,
            pre_roll_seconds=input.pre_roll_seconds,
            post_roll_seconds=input.post_roll_seconds,
            shot_count=0,
            duration_seconds=0.0,
            error=None,
            created_at=now,
            updated_at=now,
        )
        await self._sessions.add(session)
        return CreateSessionOutput(
            session_id=session_id,
            signed_upload_url=signed.url,
            expires_at=signed.expires_at,
        )
