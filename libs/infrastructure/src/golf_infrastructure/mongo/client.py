from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


def make_client(uri: str) -> AsyncIOMotorClient:
    return AsyncIOMotorClient(uri, tz_aware=True)


def get_database(client: AsyncIOMotorClient, name: str) -> AsyncIOMotorDatabase:
    return client[name]
