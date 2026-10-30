import json
import re
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from app.deps import get_current_user
from app.db.mongo import get_database, stock_by_symbol, aggregate_candles
from app.schemas.app import StockSearchResponse, StockDetail, CandleAgg
from app.core.redis import get_redis_client
from app.core.rate_limit import RateLimiter

router = APIRouter(prefix="/stocks", tags=["stocks"])

@router.get("", response_model=StockSearchResponse, dependencies=[Depends(get_current_user), Depends(RateLimiter(60, 60))])
async def search_stocks(
    search: str = Query("", description="Search by symbol or name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    redis = await get_redis_client()
    cache_key = f"stocks:search:{search}:{limit}:{offset}"
    
    # Try cache
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)
        
    escaped_search = re.escape(search)
    match = {"$or": [{"symbol": {"$regex": escaped_search, "$options": "i"}},
                      {"name": {"$regex": escaped_search, "$options": "i"}}]} if search else {}
    total = await get_database().stocks.count_documents(match)
    stocks = await get_database().stocks.find(match, {"_id": 0, "symbol": 1, "name": 1, "exchange": 1}).sort("symbol", 1).skip(offset).limit(limit).to_list(length=limit)
    
    response_data = {
        "items": [{"symbol": s["symbol"], "name": s["name"], "exchange": s["exchange"]} for s in stocks],
        "total": total
    }
    
    # Cache for 5 minutes
    await redis.setex(cache_key, 300, json.dumps(response_data))
    
    return response_data

@router.get("/{symbol}", response_model=StockDetail, dependencies=[Depends(get_current_user), Depends(RateLimiter(60, 60))])
async def get_stock_detail(symbol: str):
    stock = await stock_by_symbol(symbol)
    
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    # Get candle range and count
    agg = await get_database().candles.aggregate([{"$match": {"stock_id": stock["symbol"]}},
        {"$group": {"_id": None, "first_ts": {"$min": "$ts"}, "last_ts": {"$max": "$ts"}, "candle_count": {"$sum": 1}}}]).to_list(length=1)
    agg = agg[0] if agg else {"first_ts": None, "last_ts": None, "candle_count": 0}
    
    return {
        "symbol": stock["symbol"], "name": stock["name"], "exchange": stock["exchange"],
        "first_ts": agg["first_ts"], "last_ts": agg["last_ts"], "candle_count": agg["candle_count"]
    }

@router.get("/{symbol}/candles", response_model=List[CandleAgg], dependencies=[Depends(get_current_user), Depends(RateLimiter(60, 60))])
async def get_candles(
    symbol: str,
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    interval: str = Query("1m", pattern="^(1m|5m|15m|30m|1h)$"),
):
    if not await stock_by_symbol(symbol):
        raise HTTPException(status_code=404, detail="Stock not found")
    seconds = {"1m": 60, "5m": 300, "15m": 900, "30m": 1800, "1h": 3600}[interval]
    rows = await aggregate_candles(symbol, seconds, start=from_ts, end=to_ts)
    return [{"time": int(r["_id"].timestamp()), "open": r["open"], "high": r["high"], "low": r["low"], "close": r["close"], "volume": int(r["volume"])} for r in rows]

@router.get("/{symbol}/trading-days", response_model=List[str], dependencies=[Depends(get_current_user), Depends(RateLimiter(60, 60))])
async def get_trading_days(symbol: str):
    if not await stock_by_symbol(symbol):
        raise HTTPException(status_code=404, detail="Stock not found")
    values = await get_database().candles.aggregate([{"$match": {"stock_id": symbol.upper()}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$ts"}}}},
        {"$sort": {"_id": -1}}]).to_list(length=10000)
    return [x["_id"] for x in values]
