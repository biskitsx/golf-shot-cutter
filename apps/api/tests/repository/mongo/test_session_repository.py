from datetime import UTC, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.services.errors import SessionNotFoundError
from app.core.models.session import Session, SessionStatus
from app.repository.mongo.session_repository import MongoSessionRepository


def _make(id: str = "ses_1", user_id: str | None = None) -> Session:
    now = datetime.now(UTC)
    return Session(
        id=id,
        user_id=user_id,
        raw_video_key=f"raw/{id}/v.mp4",
        status=SessionStatus.QUEUED,
        pre_roll_seconds=2.0,
        post_roll_seconds=5.0,
        shot_count=0,
        duration_seconds=900.0,
        error=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def repo():
    db = AsyncMongoMockClient()["test"]
    return MongoSessionRepository(db)


async def test_add_then_get(repo):
    s = _make()
    await repo.add(s)
    fetched = await repo.get("ses_1")
    assert fetched.id == "ses_1"
    assert fetched.status is SessionStatus.QUEUED


async def test_get_missing_raises(repo):
    with pytest.raises(SessionNotFoundError):
        await repo.get("missing")


async def test_update_persists_status_change(repo):
    s = _make()
    await repo.add(s)
    moved = s.mark_processing(now=datetime.now(UTC))
    await repo.update(moved)
    fetched = await repo.get("ses_1")
    assert fetched.status is SessionStatus.PROCESSING


async def test_update_missing_raises(repo):
    with pytest.raises(SessionNotFoundError):
        await repo.update(_make("ses_missing"))


async def test_list_for_user_filters_correctly(repo):
    await repo.add(_make("ses_a", user_id="u_1"))
    await repo.add(_make("ses_b", user_id="u_2"))
    await repo.add(_make("ses_c", user_id=None))
    rows = await repo.list_for_user("u_1")
    assert {s.id for s in rows} == {"ses_a"}
    rows_anon = await repo.list_for_user(None)
    assert {s.id for s in rows_anon} == {"ses_c"}
