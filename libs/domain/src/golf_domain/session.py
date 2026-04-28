from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from .errors import InvalidStateTransitionError, InvalidValueError
from .ids import SessionId, UserId


class SessionStatus(StrEnum):
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class SessionError(BaseModel):
    model_config = ConfigDict(frozen=True)
    stage: str
    message: str


class Session(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: SessionId
    user_id: UserId | None
    raw_video_key: str
    status: SessionStatus
    pre_roll_seconds: float
    post_roll_seconds: float
    shot_count: int = 0
    duration_seconds: float
    error: SessionError | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.pre_roll_seconds < 0:
            raise InvalidValueError("pre_roll_seconds must be >= 0")
        if self.post_roll_seconds < 0:
            raise InvalidValueError("post_roll_seconds must be >= 0")
        if self.shot_count < 0:
            raise InvalidValueError("shot_count must be >= 0")
        if self.duration_seconds < 0:
            raise InvalidValueError("duration_seconds must be >= 0")
        return self

    def assert_editable(self) -> None:
        if self.status is not SessionStatus.READY:
            raise InvalidStateTransitionError(
                f"Session must be READY to edit (current: {self.status})"
            )

    def mark_processing(self) -> "Session":
        if self.status is not SessionStatus.QUEUED:
            raise InvalidStateTransitionError(f"Cannot mark processing from {self.status}")
        return self.model_copy(update={"status": SessionStatus.PROCESSING})

    def mark_ready(self, shot_count: int) -> "Session":
        if self.status is not SessionStatus.PROCESSING:
            raise InvalidStateTransitionError(f"Cannot mark ready from {self.status}")
        return self.model_copy(
            update={
                "status": SessionStatus.READY,
                "shot_count": shot_count,
            }
        )

    def mark_failed(self, stage: str, message: str) -> "Session":
        return self.model_copy(
            update={
                "status": SessionStatus.FAILED,
                "error": SessionError(stage=stage, message=message),
            }
        )
