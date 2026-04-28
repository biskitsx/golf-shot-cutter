from pydantic import BaseModel, ConfigDict, model_validator

from .errors import InvalidValueError


class Confidence(BaseModel):
    model_config = ConfigDict(frozen=True)
    value: float

    @model_validator(mode="after")
    def _check_range(self) -> "Confidence":
        if not 0.0 <= self.value <= 1.0:
            raise InvalidValueError(f"Confidence must be in [0, 1], got {self.value}")
        return self


class TimeRange(BaseModel):
    model_config = ConfigDict(frozen=True)
    start: float
    end: float

    @model_validator(mode="after")
    def _check_order(self) -> "TimeRange":
        if self.start >= self.end:
            raise InvalidValueError(
                f"TimeRange requires start < end (got {self.start} >= {self.end})"
            )
        return self

    @property
    def duration(self) -> float:
        return self.end - self.start
