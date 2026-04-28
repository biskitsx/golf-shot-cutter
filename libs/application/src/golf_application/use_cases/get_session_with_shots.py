from pydantic import BaseModel

from golf_domain.ids import SessionId
from golf_domain.session import Session
from golf_domain.shot import Shot

from ..ports import SessionRepository, ShotRepository


class GetSessionWithShotsInput(BaseModel):
    session_id: SessionId


class GetSessionWithShotsOutput(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    session: Session
    shots: list[Shot]


class GetSessionWithShotsUseCase:
    def __init__(self, *, sessions: SessionRepository, shots: ShotRepository) -> None:
        self._sessions = sessions
        self._shots = shots

    async def execute(self, input: GetSessionWithShotsInput) -> GetSessionWithShotsOutput:
        session = await self._sessions.get(input.session_id)
        shots = await self._shots.list_by_session(session.id)
        return GetSessionWithShotsOutput(session=session, shots=shots)
