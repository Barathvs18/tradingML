"""MongoDB persistence for users, refresh sessions, stocks and market candles."""
from datetime import datetime, timezone
from uuid import UUID
from pymongo import AsyncMongoClient
from pymongo import ASCENDING, DESCENDING, ReturnDocument
from app.core.config import settings

client: AsyncMongoClient | None = None
database = None


def get_database() -> AsyncIOMotorDatabase:
    if database is None:
        raise RuntimeError("MongoDB is not initialized")
    return database


async def connect_mongo() -> None:
    global client, database
    client = AsyncMongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000, tz_aware=True)
    await client.admin.command("ping")
    database = client[settings.MONGODB_DATABASE]
    await database.users.create_index("email", unique=True)
    await database.refresh_tokens.create_index("token_hash", unique=True)
    await database.refresh_tokens.create_index("user_id")
    await database.stocks.create_index("symbol", unique=True)
    await database.candles.create_index([("stock_id", ASCENDING), ("ts", DESCENDING)], unique=True)
    await database.candles.create_index([("stock_id", ASCENDING), ("ts", ASCENDING)])


async def close_mongo() -> None:
    global client, database
    if client:
        await client.close()
    client = None
    database = None


def user_document(document: dict | None):
    if document is None:
        return None
    from app.models.user import User
    return User(id=UUID(str(document["_id"])), email=document["email"], name=document["name"],
                password_hash=document["password_hash"], is_active=document.get("is_active", True),
                created_at=document["created_at"])


async def find_user_by_id(user_id):
    return user_document(await get_database().users.find_one({"_id": str(user_id)}))


async def find_user_by_email(email: str):
    return user_document(await get_database().users.find_one({"email": email.strip().lower()}))


async def insert_user(user):
    doc = {"_id": str(user.id), "email": user.email.lower(), "name": user.name,
           "password_hash": user.password_hash, "is_active": user.is_active,
           "created_at": user.created_at}
    await get_database().users.insert_one(doc)
    return user


async def update_user(user):
    await get_database().users.update_one({"_id": str(user.id)}, {"$set": {"name": user.name}})


async def create_refresh_token(doc):
    await get_database().refresh_tokens.insert_one(doc)


async def rotate_refresh_token(token_hash: str, new_doc: dict, now: datetime):
    """Atomically revoke one valid token and create its replacement."""
    tokens = get_database().refresh_tokens
    old = await tokens.find_one({"token_hash": token_hash})
    if not old:
        return "missing", None
    if old.get("revoked"):
        await tokens.update_many({"user_id": old["user_id"]}, {"$set": {"revoked": True}})
        return "reuse", old
    if old["expires_at"] < now:
        return "expired", old
    new_doc["user_id"] = old["user_id"]
    # Stage the replacement before the compare-and-set. On a concurrent refresh,
    # the losing request deletes its staged token and revokes the whole family.
    await tokens.insert_one(new_doc)
    replacement = await tokens.find_one_and_update(
        {"_id": old["_id"], "revoked": False, "expires_at": {"$gt": now}},
        {"$set": {"revoked": True, "replaced_by": new_doc["_id"]}},
        return_document=ReturnDocument.BEFORE)
    if replacement is None:
        # Concurrent refresh: the winning rotation marks the token revoked.
        await tokens.delete_one({"_id": new_doc["_id"]})
        await tokens.update_many({"user_id": old["user_id"]}, {"$set": {"revoked": True}})
        return "reuse", old
    return "rotated", old


async def stock_by_symbol(symbol: str):
    return await get_database().stocks.find_one({"symbol": symbol.upper()})


async def candles_for_stock(symbol: str, *, start=None, end=None, limit=None, descending=False):
    query = {"stock_id": symbol.upper()}
    bounds = {}
    if start is not None: bounds["$gte"] = start
    if end is not None: bounds["$lte"] = end
    if bounds: query["ts"] = bounds
    cursor = get_database().candles.find(query).sort("ts", DESCENDING if descending else ASCENDING)
    if limit is not None: cursor = cursor.limit(limit)
    return await cursor.to_list(length=limit or 100000)


async def aggregate_candles(symbol: str, seconds: int, *, start=None, end=None, limit=5000, descending=False):
    match = {"stock_id": symbol.upper()}
    bounds = {}
    if start is not None: bounds["$gte"] = start
    if end is not None: bounds["$lte"] = end
    if bounds: match["ts"] = bounds
    pipeline = [{"$match": match}, {"$sort": {"ts": 1}},
        {"$group": {"_id": {"$toDate": {"$subtract": [{"$toLong": "$ts"}, {"$mod": [{"$toLong": "$ts"}, seconds * 1000]}]}},
          "open": {"$first": "$open"}, "high": {"$max": "$high"}, "low": {"$min": "$low"},
          "close": {"$last": "$close"}, "volume": {"$sum": "$volume"}}},
        {"$sort": {"_id": -1 if descending else 1}}, {"$limit": limit}]
    rows = await get_database().candles.aggregate(pipeline).to_list(length=limit)
    return rows
