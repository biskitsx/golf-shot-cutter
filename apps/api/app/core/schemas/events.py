from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Camel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class SseEventEnvelope(_Camel):
    type: str
    session_id: str = Field(alias="sessionId")
    payload: dict[str, Any]
    occurred_at: datetime = Field(alias="occurredAt")
