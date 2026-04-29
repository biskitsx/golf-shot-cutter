from datetime import UTC, datetime

import pytest

from app.services.shot_service import (
    AddManualShotInput,
    DeleteShotInput,
    ShotService,
    UpdateShotBoundaryInput,
)
from app.services.errors import ShotNotFoundError
from app.core.models.session import Session, SessionStatus
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence
from app.core.models.errors import InvalidStateTransitionError, InvalidValueError
from fakes.fake_clock import FakeClock
from fakes.fake_id_generator import FakeIdGenerator
from fakes.fake_publisher import FakeEventPublisher
from fakes.fake_storage import FakeStorage
from fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _ready_session():
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=SessionStatus.READY,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _shot():
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


def _clock():
    return FakeClock(datetime(2026, 4, 27, tzinfo=UTC))


def _svc(sessions, shots, events=None, clock=None, ids=None, storage=None, celery=None):
    return ShotService(
        sessions_repo=sessions,
        shots_repo=shots,
        events=events or FakeEventPublisher(),
        storage=storage or FakeStorage(),
        celery=celery,  # not exercised by these tests
        clock=clock or _clock(),
        ids=ids or FakeIdGenerator(),
    )


# ---------- update_boundary ----------


async def test_updates_boundary_on_ready_session():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())
    await shots.add(_shot())
    svc = _svc(sessions, shots)
    out = await svc.update_boundary(
        UpdateShotBoundaryInput(session_id="ses_1", shot_id="shot_1", t_start=7.0, t_end=16.0)
    )
    assert out.t_start == 7.0
    assert out.t_end == 16.0


async def test_rejects_when_session_not_ready():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    session = Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=SessionStatus.PROCESSING,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=1,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    await sessions.add(session)
    await shots.add(_shot())
    svc = _svc(sessions, shots)
    with pytest.raises(InvalidStateTransitionError):
        await svc.update_boundary(
            UpdateShotBoundaryInput(session_id="ses_1", shot_id="shot_1", t_start=7.0, t_end=16.0)
        )


async def test_rejects_when_impact_outside_window():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())
    await shots.add(_shot())
    svc = _svc(sessions, shots)
    with pytest.raises(InvalidValueError):
        await svc.update_boundary(
            UpdateShotBoundaryInput(session_id="ses_1", shot_id="shot_1", t_start=11.0, t_end=12.0)
        )


async def test_raises_when_shot_missing():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())
    svc = _svc(sessions, shots)
    with pytest.raises(ShotNotFoundError):
        await svc.update_boundary(
            UpdateShotBoundaryInput(session_id="ses_1", shot_id="missing", t_start=7.0, t_end=16.0)
        )


# ---------- add_manual ----------


async def test_add_manual_shot_assigns_next_index():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())
    svc = _svc(sessions, shots)
    out1 = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=10.0, t_start=8.0, t_end=15.0)
    )
    out2 = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=30.0, t_start=28.0, t_end=35.0)
    )
    assert out1.index == 1
    assert out2.index == 2
    assert out1.source is ShotSource.MANUAL
    assert (await sessions.get("ses_1")).shot_count == 2


async def test_delete_shot_removes_record():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())
    svc = _svc(sessions, shots)
    out = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=10.0, t_start=8.0, t_end=15.0)
    )
    await svc.delete(DeleteShotInput(session_id="ses_1", shot_id=out.id))
    with pytest.raises(ShotNotFoundError):
        await shots.get(out.id)
    assert (await sessions.get("ses_1")).shot_count == 0


async def test_add_manual_after_delete_uses_max_plus_one():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())
    svc = _svc(sessions, shots)
    s1 = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=10, t_start=8, t_end=15)
    )
    s2 = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=20, t_start=18, t_end=25)
    )
    s3 = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=30, t_start=28, t_end=35)
    )
    assert [s1.index, s2.index, s3.index] == [1, 2, 3]
    await svc.delete(DeleteShotInput(session_id="ses_1", shot_id=s2.id))
    s4 = await svc.add_manual(
        AddManualShotInput(session_id="ses_1", t_impact=40, t_start=38, t_end=45)
    )
    assert s4.index == 4
