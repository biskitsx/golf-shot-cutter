from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from golf_api.deps.auth import current_user_id, get_container
from app.services.session_service import CreateSessionInput
from app.services.session_service import (
    GetSessionWithShotsInput,
)
from app.services.session_service import ListSessionsInput
from app.services.session_service import StartProcessingInput
from golf_contracts import (
    CreateSessionRequest,
    CreateSessionResponse,
    SessionDto,
    ShotDto,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionWithShotsResponse(BaseModel):
    session: SessionDto
    shots: list[ShotDto]
    model_config = {"populate_by_name": True}


def _session_dto(s) -> SessionDto:
    return SessionDto.model_validate(
        {
            "id": s.id,
            "userId": s.user_id,
            "rawVideoKey": s.raw_video_key,
            "status": s.status.value,
            "preRollSeconds": s.pre_roll_seconds,
            "postRollSeconds": s.post_roll_seconds,
            "shotCount": s.shot_count,
            "durationSeconds": s.duration_seconds,
            "error": ({"stage": s.error.stage, "message": s.error.message} if s.error else None),
            "createdAt": s.created_at,
            "updatedAt": s.updated_at,
        }
    )


def _shot_dto(sh) -> ShotDto:
    return ShotDto.model_validate(
        {
            "id": sh.id,
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
    )


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateSessionResponse)
async def create_session(
    req: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> CreateSessionResponse:
    out = await container.create_session.execute(
        CreateSessionInput(
            user_id=user_id,
            original_filename=req.original_filename,
            pre_roll_seconds=req.pre_roll_seconds,
            post_roll_seconds=req.post_roll_seconds,
        )
    )
    return CreateSessionResponse.model_validate(
        {
            "sessionId": out.session_id,
            "signedUploadUrl": out.signed_upload_url,
            "expiresAt": out.expires_at,
        }
    )


@router.get("", response_model=list[SessionDto])
async def list_sessions(
    user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> list[SessionDto]:
    sessions = await container.list_sessions.execute(ListSessionsInput(user_id=user_id))
    return [_session_dto(s) for s in sessions]


@router.get("/{session_id}", response_model=SessionWithShotsResponse)
async def get_session(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> SessionWithShotsResponse:
    out = await container.get_session.execute(GetSessionWithShotsInput(session_id=session_id))
    return SessionWithShotsResponse(
        session=_session_dto(out.session),
        shots=[_shot_dto(s) for s in out.shots],
    )


@router.post("/{session_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def start_processing(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> dict[str, str]:
    await container.start_processing.execute(StartProcessingInput(session_id=session_id))
    return {"status": "queued"}
