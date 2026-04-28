from datetime import UTC, datetime

from app.core.models.events import (
    SessionFailed,
    SessionProcessingStarted,
    SessionReady,
    ShotDetected,
)


def test_session_processing_started_fields():
    e = SessionProcessingStarted(
        session_id="ses_1",
        occurred_at=datetime.now(UTC),
    )
    assert e.session_id == "ses_1"


def test_shot_detected_carries_shot_id_and_confidence():
    e = ShotDetected(
        session_id="ses_1",
        shot_id="shot_1",
        confidence=0.91,
        occurred_at=datetime.now(UTC),
    )
    assert e.confidence == 0.91


def test_session_ready_carries_shot_count():
    e = SessionReady(
        session_id="ses_1",
        shot_count=12,
        occurred_at=datetime.now(UTC),
    )
    assert e.shot_count == 12


def test_session_failed_carries_stage_and_message():
    e = SessionFailed(
        session_id="ses_1",
        stage="audio_onset",
        message="sample rate too low",
        occurred_at=datetime.now(UTC),
    )
    assert e.stage == "audio_onset"
