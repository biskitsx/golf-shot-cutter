from datetime import UTC, datetime

import pytest

from golf_application.use_cases.create_session import (
    CreateSessionInput,
    CreateSessionUseCase,
)
from golf_domain.session import SessionStatus

from ..fakes.fake_clock import FakeClock
from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_storage import FakeStorage
from ..fakes.in_memory_repos import InMemorySessionRepository


@pytest.fixture
def context():
    return {
        "sessions": InMemorySessionRepository(),
        "storage": FakeStorage(),
        "clock": FakeClock(datetime(2026, 4, 27, 10, 0, tzinfo=UTC)),
        "ids": FakeIdGenerator(),
    }


async def test_creates_session_with_signed_upload_url(context):
    uc = CreateSessionUseCase(
        sessions=context["sessions"],
        storage=context["storage"],
        clock=context["clock"],
        ids=context["ids"],
    )
    out = await uc.execute(
        CreateSessionInput(
            user_id=None,
            original_filename="range.mp4",
            pre_roll_seconds=2.0,
            post_roll_seconds=5.0,
        )
    )
    assert out.session_id == "ses_0001"
    assert out.signed_upload_url.startswith("https://fake-r2.local/PUT/raw/ses_0001/range.mp4")
    persisted = await context["sessions"].get("ses_0001")
    assert persisted.status is SessionStatus.UPLOADING
    assert persisted.pre_roll_seconds == 2.0
    assert persisted.raw_video_key == "raw/ses_0001/range.mp4"


async def test_rejects_empty_filename(context):
    uc = CreateSessionUseCase(**context)
    with pytest.raises(ValueError):
        await uc.execute(
            CreateSessionInput(
                user_id=None,
                original_filename="",
                pre_roll_seconds=2.0,
                post_roll_seconds=5.0,
            )
        )
