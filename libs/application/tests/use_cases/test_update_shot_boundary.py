from datetime import UTC, datetime

import pytest

from golf_application.errors import ShotNotFoundError
from golf_application.use_cases.update_shot_boundary import (
    UpdateShotBoundaryInput,
    UpdateShotBoundaryUseCase,
)
from golf_domain.errors import InvalidStateTransitionError, InvalidValueError
from golf_domain.session import Session, SessionStatus
from golf_domain.shot import Shot, ShotSource
from golf_domain.value_objects import Confidence

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _session(status: SessionStatus = SessionStatus.READY) -> Session:
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=status,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=1,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _shot() -> Shot:
    return Shot(
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


def _clock() -> FakeClock:
    return FakeClock(datetime(2026, 4, 27, tzinfo=UTC))


async def test_updates_boundary_on_ready_session():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session())
    await shots.add(_shot())

    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher(), clock=_clock()
    )
    out = await uc.execute(
        UpdateShotBoundaryInput(session_id="ses_1", shot_id="shot_1", t_start=7.0, t_end=16.0)
    )
    assert out.t_start == 7.0
    assert out.t_end == 16.0


async def test_rejects_when_session_not_ready():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session(status=SessionStatus.PROCESSING))
    await shots.add(_shot())
    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher(), clock=_clock()
    )
    with pytest.raises(InvalidStateTransitionError):
        await uc.execute(
            UpdateShotBoundaryInput(session_id="ses_1", shot_id="shot_1", t_start=7.0, t_end=16.0)
        )


async def test_rejects_when_impact_outside_window():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session())
    await shots.add(_shot())
    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher(), clock=_clock()
    )
    with pytest.raises(InvalidValueError):
        await uc.execute(
            UpdateShotBoundaryInput(session_id="ses_1", shot_id="shot_1", t_start=11.0, t_end=12.0)
        )


async def test_raises_when_shot_missing():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session())
    uc = UpdateShotBoundaryUseCase(
        sessions=sessions, shots=shots, events=FakeEventPublisher(), clock=_clock()
    )
    with pytest.raises(ShotNotFoundError):
        await uc.execute(
            UpdateShotBoundaryInput(session_id="ses_1", shot_id="missing", t_start=7.0, t_end=16.0)
        )
