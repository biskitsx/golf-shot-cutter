from datetime import UTC, datetime

from app.core.models.session import Session, SessionError, SessionStatus
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence
from app.repository.mongo.documents import (
    session_from_doc,
    session_to_doc,
    shot_from_doc,
    shot_to_doc,
)


def _ts() -> datetime:
    return datetime(2026, 4, 28, 10, 0, tzinfo=UTC)


def test_session_round_trip():
    s = Session(
        id="ses_abc",
        user_id=None,
        raw_video_key="raw/ses_abc/v.mp4",
        status=SessionStatus.READY,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=2,
        duration_seconds=900.0,
        error=None,
        created_at=_ts(),
        updated_at=_ts(),
    )
    doc = session_to_doc(s)
    assert doc["_id"] == "ses_abc"
    assert doc["status"] == "ready"
    back = session_from_doc(doc)
    assert back == s


def test_session_round_trip_with_error():
    s = Session(
        id="ses_x",
        user_id="u_1",
        raw_video_key="raw/ses_x/v.mp4",
        status=SessionStatus.FAILED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=0.0,
        error=SessionError(stage="audio_onset", message="bad codec"),
        created_at=_ts(),
        updated_at=_ts(),
    )
    back = session_from_doc(session_to_doc(s))
    assert back.error is not None
    assert back.error.stage == "audio_onset"


def test_shot_round_trip():
    sh = Shot(
        id="shot_1",
        session_id="ses_abc",
        index=1,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.91),
        source=ShotSource.AUTO,
        clip_key="clips/ses_abc/shot_001.mp4",
        created_at=_ts(),
        updated_at=_ts(),
    )
    back = shot_from_doc(shot_to_doc(sh))
    assert back == sh
    assert back.confidence.value == 0.91
