from datetime import datetime

from pydantic import BaseModel, ConfigDict

from .ids import SessionId, ShotId


class DomainEvent(BaseModel):
    model_config = ConfigDict(frozen=True)
    session_id: SessionId
    occurred_at: datetime


class SessionProcessingStarted(DomainEvent):
    pass


class ShotDetected(DomainEvent):
    shot_id: ShotId
    confidence: float


class SessionReady(DomainEvent):
    shot_count: int


class SessionFailed(DomainEvent):
    stage: str
    message: str


class ShotBoundaryUpdated(DomainEvent):
    shot_id: ShotId
    t_start: float
    t_end: float


class ShotDeleted(DomainEvent):
    shot_id: ShotId
