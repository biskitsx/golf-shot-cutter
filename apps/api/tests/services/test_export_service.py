from datetime import UTC, datetime


from app.services.export_service import ExportService, ExportSessionZipInput
from app.core.models.session import Session, SessionStatus
from fakes.fake_id_generator import FakeIdGenerator
from fakes.fake_storage import FakeStorage
from fakes.in_memory_repos import InMemorySessionRepository


def _session(status=SessionStatus.READY):
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


async def test_export_session_zip_returns_export_id_and_signed_get():
    sessions = InMemorySessionRepository()
    await sessions.add(_session())
    svc = ExportService(sessions_repo=sessions, storage=FakeStorage(), ids=FakeIdGenerator())
    out = await svc.export(ExportSessionZipInput(session_id="ses_1"))
    assert out.export_id == "exp_0001"
    assert out.signed_download_url.startswith(
        "https://fake-r2.local/GET/exports/ses_1/exp_0001.zip"
    )
