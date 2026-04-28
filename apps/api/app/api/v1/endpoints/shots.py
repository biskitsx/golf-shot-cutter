from fastapi import APIRouter, Depends, Request, status

from app.api.v1.endpoints.sessions import _shot_dto
from app.core.schemas.shots import AddManualShotRequest, ShotDto, UpdateShotBoundaryRequest
from app.deps.auth import current_user_id
from app.services.shot_service import AddManualShotInput, DeleteShotInput, UpdateShotBoundaryInput

router = APIRouter(prefix="/sessions/{session_id}/shots", tags=["shots"])


def _get_service(request: Request):
    c = request.app.state.container
    if hasattr(c, "shot_service"):
        svc = c.shot_service
        return svc() if callable(svc) and not hasattr(svc, "update_boundary") else svc
    return c._shot_service  # noqa: SLF001


@router.patch("/{shot_id}", response_model=ShotDto)
async def update_boundary(
    session_id: str,
    shot_id: str,
    req: UpdateShotBoundaryRequest,
    request: Request,
    _user_id: str = Depends(current_user_id),
) -> ShotDto:
    svc = _get_service(request)
    shot = await svc.update_boundary(
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
    request: Request,
    _user_id: str = Depends(current_user_id),
) -> ShotDto:
    svc = _get_service(request)
    shot = await svc.add_manual(
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
    request: Request,
    _user_id: str = Depends(current_user_id),
) -> None:
    svc = _get_service(request)
    await svc.delete(DeleteShotInput(session_id=session_id, shot_id=shot_id))
