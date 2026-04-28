from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.deps.auth import current_user_id
from app.services.session_service import RequestSignedUploadUrlInput

router = APIRouter(prefix="/sessions", tags=["upload"])


class UploadUrlResponse(BaseModel):
    url: str
    expires_at: datetime = Field(alias="expiresAt")
    model_config = {"populate_by_name": True}


def _get_service(request: Request):
    c = request.app.state.container
    if hasattr(c, "session_service"):
        svc = c.session_service
        return svc() if callable(svc) and not hasattr(svc, "request_upload_url") else svc
    return c._session_service  # noqa: SLF001


@router.post(
    "/{session_id}/upload-url", response_model=UploadUrlResponse, response_model_by_alias=True
)
async def upload_url(
    session_id: str,
    request: Request,
    _user_id: str = Depends(current_user_id),
) -> UploadUrlResponse:
    svc = _get_service(request)
    signed = await svc.request_upload_url(RequestSignedUploadUrlInput(session_id=session_id))
    return UploadUrlResponse(url=signed.url, expires_at=signed.expires_at)
