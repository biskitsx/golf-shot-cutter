from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from golf_api.deps.auth import current_user_id, get_container
from golf_application.use_cases.request_signed_upload_url import (
    RequestSignedUploadUrlInput,
)


router = APIRouter(prefix="/sessions", tags=["upload"])


class UploadUrlResponse(BaseModel):
    url: str
    expires_at: datetime = Field(alias="expiresAt")
    model_config = {"populate_by_name": True}


@router.post(
    "/{session_id}/upload-url", response_model=UploadUrlResponse, response_model_by_alias=True
)
async def upload_url(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> UploadUrlResponse:
    signed = await container.request_upload_url.execute(
        RequestSignedUploadUrlInput(session_id=session_id)
    )
    return UploadUrlResponse(url=signed.url, expires_at=signed.expires_at)
