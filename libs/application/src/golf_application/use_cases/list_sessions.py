from pydantic import BaseModel

from golf_domain.ids import UserId
from golf_domain.session import Session

from ..ports import SessionRepository


class ListSessionsInput(BaseModel):
    user_id: UserId | None


class ListSessionsUseCase:
    def __init__(self, *, sessions: SessionRepository) -> None:
        self._sessions = sessions

    async def execute(self, input: ListSessionsInput) -> list[Session]:
        return await self._sessions.list_for_user(input.user_id)
