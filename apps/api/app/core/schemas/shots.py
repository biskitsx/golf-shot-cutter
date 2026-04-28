from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


ShotSource = Literal["auto", "manual"]


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
