"""Pure-Python domain models. No framework imports beyond Pydantic."""

from .errors import (
    DomainError,
    InvalidStateTransitionError,
    InvalidValueError,
)
from .events import (
    DomainEvent,
    SessionFailed,
    SessionProcessingStarted,
    SessionReady,
    ShotBoundaryUpdated,
    ShotDeleted,
    ShotDetected,
)
from .ids import ExportId, SessionId, ShotId, UserId
from .session import Session, SessionError, SessionStatus
from .shot import Shot, ShotSource
from .value_objects import Confidence, TimeRange

__all__ = [
    "Confidence",
    "DomainError",
    "DomainEvent",
    "ExportId",
    "InvalidStateTransitionError",
    "InvalidValueError",
    "Session",
    "SessionError",
    "SessionFailed",
    "SessionId",
    "SessionProcessingStarted",
    "SessionReady",
    "SessionStatus",
    "Shot",
    "ShotBoundaryUpdated",
    "ShotDeleted",
    "ShotDetected",
    "ShotId",
    "ShotSource",
    "TimeRange",
    "UserId",
]
