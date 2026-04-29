from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from app.core.container import Container
from app.core.schemas.responses import ResponseSuccess
from app.core.schemas.sessions import CreateSessionRequest
from app.deps.auth import current_user_id
from app.infrastructure.storage.r2_storage import R2Storage
from app.services.session_service import (
    CreateSessionInput,
    GetSessionWithShotsInput,
    ListSessionsInput,
    SessionService,
    StartProcessingInput,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _session_dto_dict(s) -> dict:
    return {
        "id": s.id,
        "userId": s.user_id,
        "rawVideoKey": s.raw_video_key,
        "status": s.status.value,
        "preRollSeconds": s.pre_roll_seconds,
        "postRollSeconds": s.post_roll_seconds,
        "shotCount": s.shot_count,
        "durationSeconds": s.duration_seconds,
        "error": ({"stage": s.error.stage, "message": s.error.message} if s.error else None),
        "createdAt": s.created_at.isoformat(),
        "updatedAt": s.updated_at.isoformat(),
    }


def _shot_dto_dict(sh) -> dict:
    return {
        "id": sh.id,
        "sessionId": sh.session_id,
        "index": sh.index,
        "tImpact": sh.t_impact,
        "tStart": sh.t_start,
        "tEnd": sh.t_end,
        "confidence": sh.confidence.value,
        "source": sh.source.value,
        "clipKey": sh.clip_key,
        "createdAt": sh.created_at.isoformat(),
        "updatedAt": sh.updated_at.isoformat(),
    }


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def create_session(
    req: CreateSessionRequest,
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
) -> ResponseSuccess:
    out = await service.create(
        CreateSessionInput(
            user_id=user_id,
            original_filename=req.original_filename,
            pre_roll_seconds=req.pre_roll_seconds,
            post_roll_seconds=req.post_roll_seconds,
        )
    )
    return ResponseSuccess(
        data={
            "sessionId": out.session_id,
            "signedUploadUrl": out.signed_upload_url,
            "expiresAt": out.expires_at.isoformat(),
        },
        code=201,
    )


@router.get("")
@inject
async def list_sessions(
    user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
) -> ResponseSuccess:
    sessions = await service.list(ListSessionsInput(user_id=user_id))
    return ResponseSuccess(data=[_session_dto_dict(s) for s in sessions])


@router.get("/{session_id}")
@inject
async def get_session(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
    storage: R2Storage = Depends(Provide[Container.storage_repo]),
) -> ResponseSuccess:
    out = await service.get_with_shots(GetSessionWithShotsInput(session_id=session_id))

    shots_dicts = []
    for s in out.shots:
        d = _shot_dto_dict(s)
        if s.clip_key:
            signed = await storage.signed_get_url(s.clip_key)
            d["clipUrl"] = signed.url
        else:
            d["clipUrl"] = None
        shots_dicts.append(d)

    return ResponseSuccess(
        data={
            "session": _session_dto_dict(out.session),
            "shots": shots_dicts,
        }
    )


@router.post("/{session_id}/process", status_code=status.HTTP_202_ACCEPTED)
@inject
async def start_processing(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
) -> ResponseSuccess:
    await service.start_processing(StartProcessingInput(session_id=session_id))
    return ResponseSuccess(data={"status": "queued"}, code=202)


@router.get("/{session_id}/raw-url")
@inject
async def raw_video_url(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
) -> ResponseSuccess:
    signed = await service.get_raw_video_url(GetSessionWithShotsInput(session_id=session_id))
    return ResponseSuccess(data={"url": signed.url, "expiresAt": signed.expires_at.isoformat()})
