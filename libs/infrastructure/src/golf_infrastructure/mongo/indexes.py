from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING


async def ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    await db["sessions"].create_index(
        [("userId", ASCENDING), ("createdAt", DESCENDING)],
        name="userId_createdAt",
    )
    await db["sessions"].create_index([("status", ASCENDING)], name="status")
    await db["shots"].create_index(
        [("sessionId", ASCENDING), ("index", ASCENDING)],
        name="sessionId_index",
        unique=True,
    )
