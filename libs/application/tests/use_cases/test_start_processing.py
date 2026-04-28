from datetime import UTC, datetime

import pytest

from golf_application.errors import SessionNotFoundError
from golf_application.use_cases.start_processing import (
    StartProcessingInput,
    StartProcessingUseCase,
)
from golf_domain.session import Session, SessionStatus

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_publisher import FakeEventPublisher
from ..fakes.fake_queue import FakeJobQueue
from ..fakes.in_memory_repos import InMemorySessionRepository


def _session(status: SessionStatus) -> Session:
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=status,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_enqueues_job_and_marks_processing():
    repo = InMemorySessionRepository()
    queue = FakeJobQueue()
    publisher = FakeEventPublisher()
    clock = FakeClock(datetime(2026, 4, 27, tzinfo=UTC))
    await repo.add(_session(SessionStatus.QUEUED))

    uc = StartProcessingUseCase(sessions=repo, queue=queue, events=publisher, clock=clock)
    await uc.execute(StartProcessingInput(session_id="ses_1"))

    updated = await repo.get("ses_1")
    assert updated.status is SessionStatus.PROCESSING
    assert len(queue.enqueued) == 1
    assert queue.enqueued[0].session_id == "ses_1"
    assert len(publisher.published) == 1
    assert publisher.published[0].occurred_at == clock.now()


async def test_raises_when_session_missing():
    repo = InMemorySessionRepository()
    uc = StartProcessingUseCase(
        sessions=repo,
        queue=FakeJobQueue(),
        events=FakeEventPublisher(),
        clock=FakeClock(datetime(2026, 4, 27, tzinfo=UTC)),
    )
    with pytest.raises(SessionNotFoundError):
        await uc.execute(StartProcessingInput(session_id="missing"))


async def test_uploading_session_is_promoted_to_queued_first():
    repo = InMemorySessionRepository()
    queue = FakeJobQueue()
    publisher = FakeEventPublisher()
    clock = FakeClock(datetime(2026, 4, 27, tzinfo=UTC))
    await repo.add(_session(SessionStatus.UPLOADING))

    uc = StartProcessingUseCase(sessions=repo, queue=queue, events=publisher, clock=clock)
    await uc.execute(StartProcessingInput(session_id="ses_1"))

    updated = await repo.get("ses_1")
    assert updated.status is SessionStatus.PROCESSING
