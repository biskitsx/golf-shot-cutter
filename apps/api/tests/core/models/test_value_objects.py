import pytest

from app.core.models.value_objects import Confidence, TimeRange
from app.core.models.errors import DomainError


def test_confidence_accepts_zero_and_one():
    assert Confidence(value=0.0).value == 0.0
    assert Confidence(value=1.0).value == 1.0


def test_confidence_rejects_outside_range():
    with pytest.raises(DomainError):
        Confidence(value=-0.1)
    with pytest.raises(DomainError):
        Confidence(value=1.1)


def test_time_range_requires_start_before_end():
    tr = TimeRange(start=1.0, end=2.0)
    assert tr.duration == pytest.approx(1.0)


def test_time_range_rejects_inverted_bounds():
    with pytest.raises(DomainError):
        TimeRange(start=2.0, end=1.0)
