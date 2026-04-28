from datetime import UTC, datetime

import pytest
from mongomock_motor import AsyncMongoMockClient

from app.services.errors import ShotNotFoundError
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence
from app.persistence.mongo.shot_repository import MongoShotRepository


def _shot(id: str, session_id: str, index: int) -> Shot:
    now = datetime.now(UTC)
    return Shot(
        id=id,
        session_id=session_id,
        index=index,
        t_impact=10.0,
        t_start=8.0,
        t_end=15.0,
        confidence=Confidence(value=0.9),
        source=ShotSource.AUTO,
        clip_key=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def repo():
    db = AsyncMongoMockClient()["test"]
    return MongoShotRepository(db)


async def test_add_get_round_trip(repo):
    await repo.add(_shot("shot_1", "ses_1", 1))
    fetched = await repo.get("shot_1")
    assert fetched.index == 1


async def test_get_missing_raises(repo):
    with pytest.raises(ShotNotFoundError):
        await repo.get("nope")


async def test_add_many_inserts_all(repo):
    await repo.add_many(
        [
            _shot("shot_a", "ses_1", 1),
            _shot("shot_b", "ses_1", 2),
        ]
    )
    rows = await repo.list_by_session("ses_1")
    assert [s.id for s in rows] == ["shot_a", "shot_b"]


async def test_list_by_session_sorts_by_index(repo):
    await repo.add(_shot("shot_b", "ses_1", 2))
    await repo.add(_shot("shot_a", "ses_1", 1))
    await repo.add(_shot("shot_other", "ses_2", 1))
    rows = await repo.list_by_session("ses_1")
    assert [s.index for s in rows] == [1, 2]


async def test_update_persists_changes(repo):
    s = _shot("shot_1", "ses_1", 1)
    await repo.add(s)
    moved = s.adjust_boundary(t_start=7.0, t_end=16.0, now=datetime.now(UTC))
    await repo.update(moved)
    back = await repo.get("shot_1")
    assert back.t_start == 7.0


async def test_update_missing_raises(repo):
    with pytest.raises(ShotNotFoundError):
        await repo.update(_shot("missing", "ses_1", 1))


async def test_delete_removes(repo):
    await repo.add(_shot("shot_1", "ses_1", 1))
    await repo.delete("shot_1")
    with pytest.raises(ShotNotFoundError):
        await repo.get("shot_1")


async def test_delete_missing_raises(repo):
    with pytest.raises(ShotNotFoundError):
        await repo.delete("nope")
