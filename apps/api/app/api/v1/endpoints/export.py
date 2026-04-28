from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.deps.auth import current_user_id
from app.services.export_service import ExportSessionZipInput

router = APIRouter(prefix="/sessions", tags=["export"])


class ExportResponse(BaseModel):
    export_id: str = Field(alias="exportId")
    signed_download_url: str = Field(alias="signedDownloadUrl")
    model_config = {"populate_by_name": True}


def _get_service(request: Request):
    c = request.app.state.container
    if hasattr(c, "export_service"):
        svc = c.export_service
        return svc() if callable(svc) and not hasattr(svc, "export") else svc
    return c._export_service  # noqa: SLF001


@router.post("/{session_id}/export", response_model=ExportResponse, response_model_by_alias=True)
async def export(
    session_id: str,
    request: Request,
    _user_id: str = Depends(current_user_id),
) -> ExportResponse:
    svc = _get_service(request)
    out = await svc.export(ExportSessionZipInput(session_id=session_id))
    return ExportResponse(export_id=out.export_id, signed_download_url=out.signed_download_url)
