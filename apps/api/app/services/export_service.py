from pydantic import BaseModel

from app.core.models.ids import SessionId
from app.repository.id_generator import UlidIdGenerator
from app.repository.mongo.session_repository import MongoSessionRepository
from app.repository.r2.storage_repository import R2StorageRepository


class ExportSessionZipInput(BaseModel):
    session_id: SessionId


class ExportSessionZipOutput(BaseModel):
    export_id: str
    signed_download_url: str


class ExportService:
    def __init__(
        self,
        *,
        sessions_repo: MongoSessionRepository,
        storage: R2StorageRepository,
        ids: UlidIdGenerator,
    ) -> None:
        self._sessions = sessions_repo
        self._storage = storage
        self._ids = ids

    async def export(self, input: ExportSessionZipInput) -> ExportSessionZipOutput:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        export_id = self._ids.export_id()
        key = f"exports/{session.id}/{export_id}.zip"
        signed = await self._storage.signed_get_url(key)
        return ExportSessionZipOutput(
            export_id=export_id,
            signed_download_url=signed.url,
        )
