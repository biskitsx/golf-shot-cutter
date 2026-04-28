from typing import Any

from app.core.models.session import Session, SessionError, SessionStatus
from app.core.models.shot import Shot, ShotSource
from app.core.models.value_objects import Confidence


def session_to_doc(s: Session) -> dict[str, Any]:
    return {
        "_id": s.id,
        "userId": s.user_id,
        "rawVideoKey": s.raw_video_key,
        "status": s.status.value,
        "preRollSeconds": s.pre_roll_seconds,
        "postRollSeconds": s.post_roll_seconds,
        "shotCount": s.shot_count,
        "durationSeconds": s.duration_seconds,
        "error": (
            {"stage": s.error.stage, "message": s.error.message} if s.error is not None else None
        ),
        "createdAt": s.created_at,
        "updatedAt": s.updated_at,
    }


def session_from_doc(d: dict[str, Any]) -> Session:
    err_doc = d.get("error")
    return Session(
        id=d["_id"],
        user_id=d.get("userId"),
        raw_video_key=d["rawVideoKey"],
        status=SessionStatus(d["status"]),
        pre_roll_seconds=d["preRollSeconds"],
        post_roll_seconds=d["postRollSeconds"],
        shot_count=d.get("shotCount", 0),
        duration_seconds=d["durationSeconds"],
        error=(
            SessionError(stage=err_doc["stage"], message=err_doc["message"]) if err_doc else None
        ),
        created_at=d["createdAt"],
        updated_at=d["updatedAt"],
    )


def shot_to_doc(sh: Shot) -> dict[str, Any]:
    return {
        "_id": sh.id,
        "sessionId": sh.session_id,
        "index": sh.index,
        "tImpact": sh.t_impact,
        "tStart": sh.t_start,
        "tEnd": sh.t_end,
        "confidence": sh.confidence.value,
        "source": sh.source.value,
        "clipKey": sh.clip_key,
        "createdAt": sh.created_at,
        "updatedAt": sh.updated_at,
    }


def shot_from_doc(d: dict[str, Any]) -> Shot:
    return Shot(
        id=d["_id"],
        session_id=d["sessionId"],
        index=d["index"],
        t_impact=d["tImpact"],
        t_start=d["tStart"],
        t_end=d["tEnd"],
        confidence=Confidence(value=d["confidence"]),
        source=ShotSource(d["source"]),
        clip_key=d.get("clipKey"),
        created_at=d["createdAt"],
        updated_at=d["updatedAt"],
    )
