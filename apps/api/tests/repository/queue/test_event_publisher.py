import json
from datetime import UTC, datetime

import fakeredis.aioredis

from app.core.models.events import SessionReady, ShotDetected
from app.repository.queue.event_publisher_repository import RedisEventPublisherRepository


async def test_publishes_shot_detected_to_session_channel():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pub = RedisEventPublisherRepository(r)
    pubsub = r.pubsub()
    await pubsub.subscribe("session:ses_1")

    await pub.publish(
        ShotDetected(
            session_id="ses_1",
            shot_id="shot_1",
            confidence=0.9,
            occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
        )
    )

    # consume one (subscribe ack first, then our payload)
    msg = None
    while True:
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if m is not None:
            msg = m
            break
    payload = json.loads(msg["data"])
    assert payload["type"] == "session.shot.detected"
    assert payload["sessionId"] == "ses_1"
    assert payload["payload"]["shotId"] == "shot_1"


async def test_publishes_session_ready():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    pub = RedisEventPublisherRepository(r)
    pubsub = r.pubsub()
    await pubsub.subscribe("session:ses_1")
    await pub.publish(
        SessionReady(
            session_id="ses_1",
            shot_count=3,
            occurred_at=datetime(2026, 4, 28, tzinfo=UTC),
        )
    )
    while True:
        m = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1)
        if m is not None:
            break
    payload = json.loads(m["data"])
    assert payload["type"] == "session.ready"
    assert payload["payload"]["shotCount"] == 3
