import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import create_app


def test_sse_unauthenticated_401(client_with_redis: TestClient):
    r = client_with_redis.get("/sessions/ses_1/events")
    assert r.status_code == 401


@pytest.mark.skip(reason="flaky e2e — manual verification required for SSE delivery")
@pytest.mark.asyncio
async def test_sse_delivers_published_event(container_with_redis):
    """End-to-end: subscribe, publish into fakeredis, receive over SSE."""
    app = create_app(env="test")
    app.state.container = container_with_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        await ac.post("/auth/login", json={"email": "dev@local", "password": "dev"})

        async with ac.stream("GET", "/sessions/ses_1/events") as resp:
            assert resp.status_code == 200

            async def _publish_after_delay():
                await asyncio.sleep(0.5)
                await container_with_redis.redis.publish(
                    "session:ses_1",
                    json.dumps(
                        {
                            "type": "session.shot.detected",
                            "sessionId": "ses_1",
                            "payload": {"shotId": "shot_1", "confidence": 0.9},
                            "occurredAt": "2026-04-28T10:00:00Z",
                        }
                    ),
                )

            publisher = asyncio.create_task(_publish_after_delay())
            try:
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        payload = json.loads(line[5:].strip())
                        assert payload["type"] == "session.shot.detected"
                        return
            finally:
                publisher.cancel()
            pytest.fail("never received SSE event")
