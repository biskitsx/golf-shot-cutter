from datetime import UTC, datetime

import pytest

from golf_application.errors import ShotNotFoundError
from golf_application.use_cases.add_manual_shot import (
    AddManualShotInput,
    AddManualShotUseCase,
)
from golf_application.use_cases.delete_shot import (
    DeleteShotInput,
    DeleteShotUseCase,
)
from golf_domain.session import Session, SessionStatus
from golf_domain.shot import ShotSource

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _ready_session() -> Session:
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


async def test_add_manual_shot_assigns_next_index():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())

    uc = AddManualShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )

    out1 = await uc.execute(
        AddManualShotInput(session_id="ses_1", t_impact=10.0, t_start=8.0, t_end=15.0)
    )
    out2 = await uc.execute(
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

    add = AddManualShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    out = await add.execute(
        AddManualShotInput(session_id="ses_1", t_impact=10.0, t_start=8.0, t_end=15.0)
    )

    delete = DeleteShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
    )
    await delete.execute(DeleteShotInput(session_id="ses_1", shot_id=out.id))

    with pytest.raises(ShotNotFoundError):
        await shots.get(out.id)
    assert (await sessions.get("ses_1")).shot_count == 0


async def test_add_manual_after_delete_uses_max_plus_one(monkeypatch):
    """Regression: after deleting a middle shot, next add should not collide."""
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_ready_session())

    add = AddManualShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 28, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    s1 = await add.execute(AddManualShotInput(session_id="ses_1", t_impact=10, t_start=8, t_end=15))
    s2 = await add.execute(
        AddManualShotInput(session_id="ses_1", t_impact=20, t_start=18, t_end=25)
    )
    s3 = await add.execute(
        AddManualShotInput(session_id="ses_1", t_impact=30, t_start=28, t_end=35)
    )
    assert [s1.index, s2.index, s3.index] == [1, 2, 3]

    delete = DeleteShotUseCase(
        sessions=sessions,
        shots=shots,
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 28, tzinfo=UTC)),
    )
    await delete.execute(DeleteShotInput(session_id="ses_1", shot_id=s2.id))

    s4 = await add.execute(
        AddManualShotInput(session_id="ses_1", t_impact=40, t_start=38, t_end=45)
    )
    # Before fix: would be 3 (collides with s3). After fix: 4 (max + 1).
    assert s4.index == 4
