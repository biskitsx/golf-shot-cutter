from datetime import UTC, datetime

import pytest

from golf_application.errors import SessionNotFoundError
from golf_application.use_cases.export_session_zip import (
    ExportSessionZipInput,
    ExportSessionZipUseCase,
)
from golf_application.use_cases.request_signed_upload_url import (
    RequestSignedUploadUrlInput,
    RequestSignedUploadUrlUseCase,
)
from golf_domain.session import Session, SessionStatus

from ..fakes.fake_id_generator import FakeIdGenerator
from ..fakes.fake_storage import FakeStorage
from ..fakes.in_memory_repos import InMemorySessionRepository


def _session(status: SessionStatus = SessionStatus.READY) -> Session:
    now = datetime.now(UTC)
    return Session(
        id="ses_1",
        user_id=None,
        raw_video_key="raw/ses_1/v.mp4",
        status=status,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=2,
        duration_seconds=900.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


async def test_request_upload_url_returns_signed_put():
    repo = InMemorySessionRepository()
    await repo.add(_session(status=SessionStatus.UPLOADING))
    uc = RequestSignedUploadUrlUseCase(sessions=repo, storage=FakeStorage())
    out = await uc.execute(RequestSignedUploadUrlInput(session_id="ses_1"))
    assert out.url.startswith("https://fake-r2.local/PUT/raw/ses_1/v.mp4")


async def test_request_upload_url_rejects_missing_session():
    repo = InMemorySessionRepository()
    uc = RequestSignedUploadUrlUseCase(sessions=repo, storage=FakeStorage())
    with pytest.raises(SessionNotFoundError):
        await uc.execute(RequestSignedUploadUrlInput(session_id="missing"))


async def test_export_session_zip_returns_export_id_and_signed_get():
    repo = InMemorySessionRepository()
    await repo.add(_session())
    uc = ExportSessionZipUseCase(sessions=repo, storage=FakeStorage(), ids=FakeIdGenerator())
    out = await uc.execute(ExportSessionZipInput(session_id="ses_1"))
    assert out.export_id == "exp_0001"
    assert out.signed_download_url.startswith(
        "https://fake-r2.local/GET/exports/ses_1/exp_0001.zip"
    )
