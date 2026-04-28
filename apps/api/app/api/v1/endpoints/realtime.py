import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.deps.auth import current_user_id

router = APIRouter(prefix="/sessions", tags=["realtime"])


def _get_redis(request: Request):
    c = request.app.state.container
    return c.redis


@router.get("/{session_id}/events")
async def stream_events(
    session_id: str,
    request: Request,
    _user_id: str = Depends(current_user_id),
) -> EventSourceResponse:
    redis_client = _get_redis(request)
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"session:{session_id}")

    async def _events() -> AsyncIterator[dict]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg is None:
                    await asyncio.sleep(0)
                    continue
                yield {"data": msg["data"]}
        finally:
            await pubsub.unsubscribe(f"session:{session_id}")
            await pubsub.aclose()

    return EventSourceResponse(_events())
