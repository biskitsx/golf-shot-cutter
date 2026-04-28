from datetime import UTC, datetime

import pytest

from golf_domain.errors import InvalidStateTransitionError, InvalidValueError
from golf_domain.session import Session, SessionStatus


def _make(**overrides):
    base = dict(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/video.mp4",
        status=SessionStatus.QUEUED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return Session(**base)


def test_session_can_be_created_in_queued_status():
    s = _make()
    assert s.status is SessionStatus.QUEUED


def test_pre_roll_must_be_non_negative():
    with pytest.raises(InvalidValueError):
        _make(pre_roll_seconds=-0.1)


def test_post_roll_must_be_non_negative():
    with pytest.raises(InvalidValueError):
        _make(post_roll_seconds=-0.1)


def test_assert_editable_passes_when_ready():
    s = _make(status=SessionStatus.READY)
    s.assert_editable()  # no raise


def test_assert_editable_rejects_when_processing():
    s = _make(status=SessionStatus.PROCESSING)
    with pytest.raises(InvalidStateTransitionError):
        s.assert_editable()


def test_mark_processing_from_queued_succeeds():
    s = _make(status=SessionStatus.QUEUED)
    moved = s.mark_processing()
    assert moved.status is SessionStatus.PROCESSING


def test_mark_processing_from_ready_rejects():
    s = _make(status=SessionStatus.READY)
    with pytest.raises(InvalidStateTransitionError):
        s.mark_processing()
