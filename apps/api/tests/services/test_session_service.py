from datetime import UTC, datetime

import pytest

from app.services.session_service import (
    CreateSessionInput,
    GetSessionWithShotsInput,
    ListSessionsInput,
    RequestSignedUploadUrlInput,
    SessionService,
    StartProcessingInput,
)
from app.services.errors import SessionNotFoundError
from app.core.models.session import SessionStatus
from fakes.fake_clock import FakeClock
from fakes.fake_id_generator import FakeIdGenerator
from fakes.fake_storage import FakeStorage
from fakes.fake_publisher import FakeEventPublisher
from fakes.fake_queue import FakeJobQueue
from fakes.in_memory_repos import InMemorySessionRepository, InMemoryShotRepository


def _make_service(
    sessions=None, shots=None, storage=None, queue=None, events=None, clock=None, ids=None
):
    return SessionService(
        sessions_repo=sessions or InMemorySessionRepository(),
        shots_repo=shots or InMemoryShotRepository(),
        storage=storage or FakeStorage(),
        queue=queue or FakeJobQueue(),
        events=events or FakeEventPublisher(),
        clock=clock or FakeClock(datetime(2026, 4, 27, 10, 0, tzinfo=UTC)),
        ids=ids or FakeIdGenerator(),
    )


# ---------- create ----------


async def test_creates_session_with_signed_upload_url():
    sessions = InMemorySessionRepository()
    svc = _make_service(sessions=sessions)
    out = await svc.create(
        CreateSessionInput(
            user_id=None,
            original_filename="range.mp4",
            pre_roll_seconds=2.0,
            post_roll_seconds=5.0,
        )
    )
    assert out.session_id == "ses_0001"
    assert out.signed_upload_url.startswith("https://fake-r2.local/PUT/raw/ses_0001/range.mp4")
    persisted = await sessions.get("ses_0001")
    assert persisted.status is SessionStatus.UPLOADING
    assert persisted.pre_roll_seconds == 2.0
    assert persisted.raw_video_key == "raw/ses_0001/range.mp4"


async def test_rejects_empty_filename():
    svc = _make_service()
    with pytest.raises(ValueError):
        await svc.create(
            CreateSessionInput(
                user_id=None,
                original_filename="",
                pre_roll_seconds=2.0,
                post_roll_seconds=5.0,
            )
        )


# ---------- start_processing ----------


def _queued_session():
    from app.core.models.session import Session

    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=SessionStatus.QUEUED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


async def test_start_processing_enqueues_job_and_marks_processing():
    sessions = InMemorySessionRepository()
    queue = FakeJobQueue()
    publisher = FakeEventPublisher()
    clock = FakeClock(datetime(2026, 4, 27, tzinfo=UTC))
    await sessions.add(_queued_session())

    svc = _make_service(sessions=sessions, queue=queue, events=publisher, clock=clock)
    await svc.start_processing(StartProcessingInput(session_id="ses_1"))

    updated = await sessions.get("ses_1")
    assert updated.status is SessionStatus.PROCESSING
    assert len(queue.enqueued) == 1
    assert queue.enqueued[0].session_id == "ses_1"
    assert len(publisher.published) == 1
    assert publisher.published[0].occurred_at == clock.now()


async def test_start_processing_raises_when_session_missing():
    svc = _make_service()
    with pytest.raises(SessionNotFoundError):
        await svc.start_processing(StartProcessingInput(session_id="missing"))


async def test_uploading_session_is_promoted_to_queued_first():
    from app.core.models.session import Session

    sessions = InMemorySessionRepository()
    await sessions.add(
        Session(
            id="ses_1",
            user_id=None,
            raw_video_key="raw/ses_1/v.mp4",
            status=SessionStatus.UPLOADING,
            pre_roll_seconds=2.0,
            post_roll_seconds=5.0,
            shot_count=0,
            duration_seconds=900.0,
            error=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    queue = FakeJobQueue()
    svc = _make_service(sessions=sessions, queue=queue)
    await svc.start_processing(StartProcessingInput(session_id="ses_1"))
    updated = await sessions.get("ses_1")
    assert updated.status is SessionStatus.PROCESSING


# ---------- list + get_with_shots ----------


def _session_obj(id_: str, user_id=None):
    from app.core.models.session import Session

    now = datetime.now(UTC)
    return Session(
        id=id_,
        user_id=user_id,
        raw_video_key=f"raw/{id_}/v.mp4",
        status=SessionStatus.READY,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


async def test_list_sessions_filters_by_user():
    sessions = InMemorySessionRepository()
    await sessions.add(_session_obj("ses_1", user_id="u_1"))
    await sessions.add(_session_obj("ses_2", user_id="u_2"))
    await sessions.add(_session_obj("ses_3", user_id=None))
    svc = _make_service(sessions=sessions)
    out = await svc.list(ListSessionsInput(user_id="u_1"))
    assert [s.id for s in out] == ["ses_1"]


async def test_get_session_returns_session_and_shots():
    from app.core.models.shot import Shot, ShotSource
    from app.core.models.value_objects import Confidence

    sessions = InMemorySessionRepository()
    shots = InMemoryShotRepository()
    await sessions.add(_session_obj("ses_1"))
    now = datetime.now(UTC)
    await shots.add(
        Shot(
            id="shot_2",
            session_id="ses_1",
            index=2,
            t_impact=20.0,
            t_start=18.0,
            t_end=25.0,
            confidence=Confidence(value=0.9),
            source=ShotSource.AUTO,
            clip_key=None,
            created_at=now,
            updated_at=now,
        )
    )
    await shots.add(
        Shot(
            id="shot_1",
            session_id="ses_1",
            index=1,
            t_impact=10.0,
            t_start=8.0,
            t_end=15.0,
            confidence=Confidence(value=0.9),
            source=ShotSource.AUTO,
            clip_key=None,
            created_at=now,
            updated_at=now,
        )
    )
    svc = _make_service(sessions=sessions, shots=shots)
    out = await svc.get_with_shots(GetSessionWithShotsInput(session_id="ses_1"))
    assert out.session.id == "ses_1"
    assert [s.id for s in out.shots] == ["shot_1", "shot_2"]


async def test_get_session_raises_when_missing():
    svc = _make_service()
    with pytest.raises(SessionNotFoundError):
        await svc.get_with_shots(GetSessionWithShotsInput(session_id="missing"))


# ---------- request_upload_url ----------


async def test_request_upload_url_returns_signed_put():
    from app.core.models.session import Session

    sessions = InMemorySessionRepository()
    await sessions.add(
        Session(
            id="ses_1",
            user_id=None,
            raw_video_key="raw/ses_1/v.mp4",
            status=SessionStatus.UPLOADING,
            pre_roll_seconds=2.0,
            post_roll_seconds=5.0,
            shot_count=0,
            duration_seconds=900.0,
            error=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    svc = _make_service(sessions=sessions)
    out = await svc.request_upload_url(RequestSignedUploadUrlInput(session_id="ses_1"))
    assert out.url.startswith("https://fake-r2.local/PUT/raw/ses_1/v.mp4")


async def test_request_upload_url_rejects_missing_session():
    svc = _make_service()
    with pytest.raises(SessionNotFoundError):
        await svc.request_upload_url(RequestSignedUploadUrlInput(session_id="missing"))
