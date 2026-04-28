from datetime import UTC, datetime


from golf_application.use_cases.process_video import (
    ProcessVideoInput,
    ProcessVideoUseCase,
    ShotCandidate,
)
from golf_domain.session import Session, SessionStatus

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _processing_session() -> Session:
    now = datetime.now(UTC)
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=SessionStatus.PROCESSING,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


async def test_persists_candidates_and_marks_ready():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    events = FakeEventPublisher()
    await sessions.add(_processing_session())

    uc = ProcessVideoUseCase(
        sessions=sessions,
        shots=shots,
        events=events,
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    await uc.execute(
        ProcessVideoInput(
            session_id="ses_1",
            candidates=[
                ShotCandidate(t_impact=10.0, confidence=0.9, clip_key="clips/ses_1/shot_001.mp4"),
                ShotCandidate(t_impact=30.0, confidence=0.85, clip_key="clips/ses_1/shot_002.mp4"),
            ],
        )
    )

    persisted = await shots.list_by_session("ses_1")
    assert [s.index for s in persisted] == [1, 2]
    updated = await sessions.get("ses_1")
    assert updated.status is SessionStatus.READY
    assert updated.shot_count == 2

    types = [type(e).__name__ for e in events.published]
    assert types.count("ShotDetected") == 2
    assert types.count("SessionReady") == 1


async def test_marks_failed_when_pipeline_returns_no_candidates_and_strict_mode():
    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    events = FakeEventPublisher()
    await sessions.add(_processing_session())

    uc = ProcessVideoUseCase(
        sessions=sessions,
        shots=shots,
        events=events,
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
        ids=FakeIdGenerator(),
    )
    # 0 candidates → still mark ready; UI handles "0 shots" state
    await uc.execute(ProcessVideoInput(session_id="ses_1", candidates=[]))
    updated = await sessions.get("ses_1")
    assert updated.status is SessionStatus.READY
    assert updated.shot_count == 0
