from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


SessionStatus = Literal["uploading", "queued", "processing", "ready", "failed"]
ShotSource = Literal["auto", "manual"]


class SessionError(_Camel):
    stage: str
    message: str


class SessionDto(_Camel):
    id: str
    user_id: str | None = Field(alias="userId")
    raw_video_key: str = Field(alias="rawVideoKey")
    status: SessionStatus
    pre_roll_seconds: float = Field(ge=0, alias="preRollSeconds")
    post_roll_seconds: float = Field(ge=0, alias="postRollSeconds")
    shot_count: int = Field(ge=0, alias="shotCount")
    duration_seconds: float = Field(ge=0, alias="durationSeconds")
    error: SessionError | None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class CreateSessionRequest(_Camel):
    original_filename: str = Field(min_length=1, alias="originalFilename")
    pre_roll_seconds: float = Field(default=2.0, ge=0, alias="preRollSeconds")
    post_roll_seconds: float = Field(default=5.0, ge=0, alias="postRollSeconds")


class CreateSessionResponse(_Camel):
    session_id: str = Field(alias="sessionId")
    signed_upload_url: str = Field(alias="signedUploadUrl")
    expires_at: datetime = Field(alias="expiresAt")


class ShotDto(_Camel):
    id: str
    session_id: str = Field(alias="sessionId")
    index: int = Field(gt=0)
    t_impact: float = Field(ge=0, alias="tImpact")
    t_start: float = Field(ge=0, alias="tStart")
    t_end: float = Field(ge=0, alias="tEnd")
    confidence: float = Field(ge=0, le=1)
    source: ShotSource
    clip_key: str | None = Field(alias="clipKey")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class UpdateShotBoundaryRequest(_Camel):
    t_start: float = Field(ge=0, alias="tStart")
    t_end: float = Field(ge=0, alias="tEnd")


class AddManualShotRequest(_Camel):
    t_impact: float = Field(ge=0, alias="tImpact")
    t_start: float = Field(ge=0, alias="tStart")
    t_end: float = Field(ge=0, alias="tEnd")


class SseEventEnvelope(_Camel):
    type: str
    session_id: str = Field(alias="sessionId")
    payload: dict[str, Any]
    occurred_at: datetime = Field(alias="occurredAt")
