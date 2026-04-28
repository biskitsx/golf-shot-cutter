from fastapi import APIRouter, Depends, status

from golf_api.deps.auth import current_user_id, get_container
from golf_api.routers.sessions import _shot_dto
from app.services.shot_service import AddManualShotInput
from app.services.shot_service import DeleteShotInput
from app.services.shot_service import (
    UpdateShotBoundaryInput,
)
from golf_contracts import (
    AddManualShotRequest,
    ShotDto,
    UpdateShotBoundaryRequest,
)


router = APIRouter(prefix="/sessions/{session_id}/shots", tags=["shots"])


@router.patch("/{shot_id}", response_model=ShotDto)
async def update_boundary(
    session_id: str,
    shot_id: str,
    req: UpdateShotBoundaryRequest,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> ShotDto:
    shot = await container.update_shot_boundary.execute(
        UpdateShotBoundaryInput(
            session_id=session_id,
            shot_id=shot_id,
            t_start=req.t_start,
            t_end=req.t_end,
        )
    )
    return _shot_dto(shot)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ShotDto)
async def add_manual(
    session_id: str,
    req: AddManualShotRequest,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> ShotDto:
    shot = await container.add_manual_shot.execute(
        AddManualShotInput(
            session_id=session_id,
            t_impact=req.t_impact,
            t_start=req.t_start,
            t_end=req.t_end,
        )
    )
    return _shot_dto(shot)


@router.delete("/{shot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shot(
    session_id: str,
    shot_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> None:
    await container.delete_shot.execute(DeleteShotInput(session_id=session_id, shot_id=shot_id))
