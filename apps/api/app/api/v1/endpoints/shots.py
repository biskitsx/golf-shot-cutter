from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from app.api.v1.endpoints.sessions import _shot_dto_dict
from app.core.container import Container
from app.core.schemas.responses import ResponseSuccess
from app.core.schemas.shots import AddManualShotRequest, UpdateShotBoundaryRequest
from app.deps.auth import current_user_id
from app.services.shot_service import (
    AddManualShotInput,
    DeleteShotInput,
    GetPoseClipInput,
    ShotService,
    UpdateShotBoundaryInput,
)

router = APIRouter(prefix="/sessions/{session_id}/shots", tags=["shots"])


@router.patch("/{shot_id}")
@inject
async def update_boundary(
    session_id: str,
    shot_id: str,
    req: UpdateShotBoundaryRequest,
    _user_id: str = Depends(current_user_id),
    service: ShotService = Depends(Provide[Container.shot_service]),
) -> ResponseSuccess:
    shot = await service.update_boundary(
        UpdateShotBoundaryInput(
            session_id=session_id,
            shot_id=shot_id,
            t_start=req.t_start,
            t_end=req.t_end,
        )
    )
    return ResponseSuccess(data=_shot_dto_dict(shot))


@router.post("", status_code=status.HTTP_201_CREATED)
@inject
async def add_manual(
    session_id: str,
    req: AddManualShotRequest,
    _user_id: str = Depends(current_user_id),
    service: ShotService = Depends(Provide[Container.shot_service]),
) -> ResponseSuccess:
    shot = await service.add_manual(
        AddManualShotInput(
            session_id=session_id,
            t_impact=req.t_impact,
            t_start=req.t_start,
            t_end=req.t_end,
        )
    )
    return ResponseSuccess(data=_shot_dto_dict(shot), code=201)


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_shot(
    session_id: str,
    shot_id: str,
    _user_id: str = Depends(current_user_id),
    service: ShotService = Depends(Provide[Container.shot_service]),
) -> None:
    await service.delete(DeleteShotInput(session_id=session_id, shot_id=shot_id))


@router.post("/{shot_id}/pose-clip")
@inject
async def get_pose_clip(
    session_id: str,
    shot_id: str,
    _user_id: str = Depends(current_user_id),
    service: ShotService = Depends(Provide[Container.shot_service]),
) -> ResponseSuccess:
    signed = await service.get_pose_clip(
        GetPoseClipInput(session_id=session_id, shot_id=shot_id)
    )
    return ResponseSuccess(
        data={"url": signed.url, "expiresAt": signed.expires_at.isoformat()}
    )
