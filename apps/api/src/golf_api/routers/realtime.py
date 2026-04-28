import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from golf_api.deps.auth import current_user_id, get_container


router = APIRouter(prefix="/sessions", tags=["realtime"])


@router.get("/{session_id}/events")
async def stream_events(
    session_id: str,
    request: Request,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> EventSourceResponse:
    pubsub = container.redis.pubsub()
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
