from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from golf_api.deps.auth import current_user_id, get_container
from golf_application.use_cases.export_session_zip import (
    ExportSessionZipInput,
)


router = APIRouter(prefix="/sessions", tags=["export"])


class ExportResponse(BaseModel):
    export_id: str = Field(alias="exportId")
    signed_download_url: str = Field(alias="signedDownloadUrl")
    model_config = {"populate_by_name": True}


@router.post("/{session_id}/export", response_model=ExportResponse, response_model_by_alias=True)
async def export(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    container=Depends(get_container),
) -> ExportResponse:
    out = await container.export_session_zip.execute(ExportSessionZipInput(session_id=session_id))
    return ExportResponse(export_id=out.export_id, signed_download_url=out.signed_download_url)
