from motor.motor_asyncio import AsyncIOMotorDatabase

from golf_application.errors import ShotNotFoundError
from golf_domain.ids import SessionId, ShotId
from golf_domain.shot import Shot

from .documents import shot_from_doc, shot_to_doc


class MongoShotRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db["shots"]

    async def add(self, shot: Shot) -> None:
        await self._col.insert_one(shot_to_doc(shot))

    async def add_many(self, shots: list[Shot]) -> None:
        if not shots:
            return
        await self._col.insert_many([shot_to_doc(s) for s in shots])

    async def get(self, shot_id: ShotId) -> Shot:
        doc = await self._col.find_one({"_id": shot_id})
        if doc is None:
            raise ShotNotFoundError(shot_id)
        return shot_from_doc(doc)

    async def list_by_session(self, session_id: SessionId) -> list[Shot]:
        cursor = self._col.find({"sessionId": session_id}).sort("index", 1)
        return [shot_from_doc(d) async for d in cursor]

    async def update(self, shot: Shot) -> None:
        result = await self._col.replace_one({"_id": shot.id}, shot_to_doc(shot))
        if result.matched_count == 0:
            raise ShotNotFoundError(shot.id)

    async def delete(self, shot_id: ShotId) -> None:
        result = await self._col.delete_one({"_id": shot_id})
        if result.deleted_count == 0:
            raise ShotNotFoundError(shot_id)
