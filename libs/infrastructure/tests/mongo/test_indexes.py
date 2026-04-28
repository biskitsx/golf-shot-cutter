import pytest
from mongomock_motor import AsyncMongoMockClient

from golf_infrastructure.mongo.indexes import ensure_indexes


@pytest.fixture
def db():
    return AsyncMongoMockClient()["test"]


async def test_ensure_indexes_creates_expected_keys(db):
    await ensure_indexes(db)
    sess_indexes = await db["sessions"].index_information()
    shot_indexes = await db["shots"].index_information()
    # session index on (userId, createdAt desc) — name varies; check at least one exists for userId
    assert any("userId" in info["key"][0] for info in sess_indexes.values() if info.get("key"))
    # shot index on (sessionId, index)
    assert any(
        "sessionId" in [pair[0] for pair in info["key"]]
        for info in shot_indexes.values()
        if info.get("key")
    )


async def test_ensure_indexes_is_idempotent(db):
    await ensure_indexes(db)
    await ensure_indexes(db)  # no error on second run
