from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.core.container import Container
from app.core.schemas.responses import ResponseSuccess
from app.deps.auth import current_user_id
from app.services.session_service import (
    RequestSignedUploadUrlInput,
    SessionService,
)


router = APIRouter(prefix="/sessions", tags=["upload"])


@router.post("/{session_id}/upload-url")
@inject
async def upload_url(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    service: SessionService = Depends(Provide[Container.session_service]),
) -> ResponseSuccess:
    signed = await service.request_upload_url(RequestSignedUploadUrlInput(session_id=session_id))
    return ResponseSuccess(data={"url": signed.url, "expiresAt": signed.expires_at.isoformat()})
