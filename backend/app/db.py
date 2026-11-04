from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings

_client: AsyncIOMotorClient | None = None


async def connect_db() -> AsyncIOMotorDatabase:
    global _client
    _client = AsyncIOMotorClient(settings.mongo_url, serverSelectionTimeoutMS=3000)
    await _client.admin.command("ping")
    db = _client[settings.mongo_db]
    await db.poi.create_index([("location", "2dsphere")])
    await db.poi_localizations.create_index([("poi_id", 1), ("lang", 1)], unique=True)
    return db


def get_db() -> AsyncIOMotorDatabase:
    assert _client is not None, "DB chưa kết nối"
    return _client[settings.mongo_db]


async def close_db() -> None:
    if _client is not None:
        _client.close()
