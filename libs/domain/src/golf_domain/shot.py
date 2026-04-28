from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from .errors import InvalidValueError
from .ids import SessionId, ShotId
from .value_objects import Confidence


class ShotSource(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"


class Shot(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: ShotId
    session_id: SessionId
    index: int
    t_impact: float
    t_start: float
    t_end: float
    confidence: Confidence
    source: ShotSource
    clip_key: str | None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def _check_invariants(self) -> Self:
        if self.index <= 0:
            raise InvalidValueError("index must be a positive integer")
        if self.t_start >= self.t_impact:
            raise InvalidValueError("t_start must be < t_impact")
        if self.t_impact >= self.t_end:
            raise InvalidValueError("t_impact must be < t_end")
        return self

    def adjust_boundary(self, *, t_start: float, t_end: float) -> "Shot":
        if t_end - t_start <= 0:
            raise InvalidValueError("Shot duration must be positive")
        if not (t_start < self.t_impact < t_end):
            raise InvalidValueError(
                f"Impact ({self.t_impact}) must lie within [{t_start}, {t_end}]"
            )
        return self.model_copy(update={"t_start": t_start, "t_end": t_end})

    def attach_clip(self, clip_key: str) -> "Shot":
        return self.model_copy(update={"clip_key": clip_key})
