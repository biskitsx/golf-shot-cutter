from pydantic import BaseModel

from golf_domain.ids import SessionId

from ..ports import IdGenerator, SessionRepository, StorageGateway


class ExportSessionZipInput(BaseModel):
    session_id: SessionId


class ExportSessionZipOutput(BaseModel):
    export_id: str
    signed_download_url: str


class ExportSessionZipUseCase:
    """
    Phase 1 minimal version: returns signed GET URL for a deterministic key.
    Plan 2 will wire this to a real ZIP-builder Celery task; for now the URL
    points at the location the worker will eventually upload to.
    """

    def __init__(
        self,
        *,
        sessions: SessionRepository,
        storage: StorageGateway,
        ids: IdGenerator,
    ) -> None:
        self._sessions = sessions
        self._storage = storage
        self._ids = ids

    async def execute(self, input: ExportSessionZipInput) -> ExportSessionZipOutput:
        session = await self._sessions.get(input.session_id)
        session.assert_editable()
        export_id = self._ids.export_id()
        key = f"exports/{session.id}/{export_id}.zip"
        signed = await self._storage.signed_get_url(key)
        return ExportSessionZipOutput(export_id=export_id, signed_download_url=signed.url)
