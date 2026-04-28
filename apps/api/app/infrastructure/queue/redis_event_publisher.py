import json

import redis.asyncio as redis_async

from app.core.models.events import (
    DomainEvent,
    SessionFailed,
    SessionProcessingStarted,
    SessionReady,
    ShotBoundaryUpdated,
    ShotDeleted,
    ShotDetected,
)


_TYPE_MAP: dict[type[DomainEvent], str] = {
    SessionProcessingStarted: "session.processing.started",
    ShotDetected: "session.shot.detected",
    SessionReady: "session.ready",
    SessionFailed: "session.failed",
    ShotBoundaryUpdated: "session.shot.boundary.updated",
    ShotDeleted: "session.shot.deleted",
}


def _payload_for(e: DomainEvent) -> dict:
    if isinstance(e, ShotDetected):
        return {"shotId": e.shot_id, "confidence": e.confidence}
    if isinstance(e, SessionReady):
        return {"shotCount": e.shot_count}
    if isinstance(e, SessionFailed):
        return {"stage": e.stage, "message": e.message}
    if isinstance(e, ShotBoundaryUpdated):
        return {"shotId": e.shot_id, "tStart": e.t_start, "tEnd": e.t_end}
    if isinstance(e, ShotDeleted):
        return {"shotId": e.shot_id}
    return {}


class RedisEventPublisher:
    def __init__(self, client: redis_async.Redis) -> None:
        self._client = client

    async def publish(self, event: DomainEvent) -> None:
        envelope = {
            "type": _TYPE_MAP[type(event)],
            "sessionId": event.session_id,
            "payload": _payload_for(event),
            "occurredAt": event.occurred_at.isoformat(),
        }
        channel = f"session:{event.session_id}"
        await self._client.publish(channel, json.dumps(envelope))
