from pydantic import BaseModel, Field


class Onset(BaseModel):
    """A candidate impact moment detected from audio (or other signals)."""

    t: float = Field(ge=0.0)
    confidence: float = Field(ge=0.0, le=1.0)


class ClipResult(BaseModel):
    """Output of cutting a single clip from the source video."""

    t_start: float = Field(ge=0.0)
    t_end: float
    clip_path: str
    clip_key: str
