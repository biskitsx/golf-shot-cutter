import asyncio
from collections.abc import AsyncIterator

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sse_starlette.sse import EventSourceResponse

from app.core.container import Container
from app.deps.auth import current_user_id


router = APIRouter(prefix="/sessions", tags=["realtime"])


@router.get("/{session_id}/events")
@inject
async def stream_events(
    session_id: str,
    request: Request,
    _user_id: str = Depends(current_user_id),
    redis: Redis = Depends(Provide[Container.redis]),
) -> EventSourceResponse:
    pubsub = redis.pubsub()
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
