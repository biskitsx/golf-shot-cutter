from datetime import UTC, datetime

import pytest

from golf_domain.errors import InvalidValueError
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence


def _make(**overrides):
    base = dict(
        id="shot_1",
        session_id="ses_1",
        index=1,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.9),
        source=ShotSource.AUTO,
        clip_key=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    base.update(overrides)
    return Shot(**base)


def test_shot_requires_t_start_before_impact_before_t_end():
    with pytest.raises(InvalidValueError):
        _make(t_start=11.0)  # after impact
    with pytest.raises(InvalidValueError):
        _make(t_end=9.0)  # before impact


def test_adjust_boundary_updates_when_valid():
    s = _make()
    now = datetime.now(UTC)
    moved = s.adjust_boundary(t_start=7.0, t_end=16.0, now=now)
    assert moved.t_start == 7.0
    assert moved.t_end == 16.0


def test_adjust_boundary_refreshes_updated_at():
    s = _make()
    later = datetime(2030, 1, 1, tzinfo=UTC)
    moved = s.adjust_boundary(t_start=7.0, t_end=16.0, now=later)
    assert moved.updated_at == later
    assert moved.updated_at != s.updated_at


def test_adjust_boundary_rejects_zero_duration():
    s = _make()
    with pytest.raises(InvalidValueError):
        s.adjust_boundary(t_start=10.0, t_end=10.0, now=datetime.now(UTC))


def test_adjust_boundary_rejects_when_impact_outside_window():
    s = _make()
    with pytest.raises(InvalidValueError):
        s.adjust_boundary(t_start=11.0, t_end=12.0, now=datetime.now(UTC))


def test_index_must_be_positive():
    with pytest.raises(InvalidValueError):
        _make(index=0)
