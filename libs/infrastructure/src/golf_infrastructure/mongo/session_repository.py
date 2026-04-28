from motor.motor_asyncio import AsyncIOMotorDatabase

from golf_application.errors import SessionNotFoundError
from golf_domain.ids import SessionId, UserId
from golf_domain.session import Session

from .documents import session_from_doc, session_to_doc


class MongoSessionRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["sessions"]

    async def add(self, session: Session) -> None:
        await self._col.insert_one(session_to_doc(session))

    async def get(self, session_id: SessionId) -> Session:
        doc = await self._col.find_one({"_id": session_id})
        if doc is None:
            raise SessionNotFoundError(session_id)
        return session_from_doc(doc)

    async def list_for_user(self, user_id: UserId | None) -> list[Session]:
        cursor = self._col.find({"userId": user_id}).sort("createdAt", -1)
        return [session_from_doc(d) async for d in cursor]

    async def update(self, session: Session) -> None:
        result = await self._col.replace_one({"_id": session.id}, session_to_doc(session))
        if result.matched_count == 0:
            raise SessionNotFoundError(session.id)
