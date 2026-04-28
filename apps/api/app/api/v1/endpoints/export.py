from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from app.core.container import Container
from app.core.schemas.responses import ResponseSuccess
from app.deps.auth import current_user_id
from app.services.export_service import ExportService, ExportSessionZipInput


router = APIRouter(prefix="/sessions", tags=["export"])


@router.post("/{session_id}/export")
@inject
async def export(
    session_id: str,
    _user_id: str = Depends(current_user_id),
    service: ExportService = Depends(Provide[Container.export_service]),
) -> ResponseSuccess:
    out = await service.export(ExportSessionZipInput(session_id=session_id))
    return ResponseSuccess(
        data={"exportId": out.export_id, "signedDownloadUrl": out.signed_download_url}
    )
