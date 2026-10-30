import json
import hashlib
import time
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from datetime import time as clock_time
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Response
from app.deps import get_current_user
from app.db.mongo import stock_by_symbol, candles_for_stock, aggregate_candles, get_database
from app.models.user import User
from app.schemas.predict import PredictRequest, PredictResponse, IntradayPredictRequest
from app.schemas.app import CandleAgg
from app.algorithms.registry import ALGORITHMS
from app.core.redis import get_redis_client
from app.core.rate_limit import RateLimiter
from app.core.logger import log_prediction

router = APIRouter(prefix="/predict", tags=["predict"])
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_OPEN = clock_time(7, 30)
MARKET_CLOSE = clock_time(13, 59)

def run_algo_sync(algo_meta, df, params):
    algo_class = algo_meta["class"]
    if "pretrained_config" in algo_meta:
        algo_instance = algo_class(key=algo_meta["key"], config=algo_meta["pretrained_config"])
    else:
        algo_instance = algo_class(key=algo_meta["key"], lookback_minutes=algo_meta["lookback_minutes"])
    return algo_instance.run(df, params)


@router.post("/intraday", dependencies=[Depends(RateLimiter(20, 60))])
async def predict_intraday(
    request: IntradayPredictRequest,
    current_user: User = Depends(get_current_user),
):
    """Return an indicator signal from the newest stored intraday candles.

    This endpoint never creates a synthetic price forecast. A live result requires
    a broker/data-provider ingestion service to keep the candles table current.
    """
    del current_user  # Authentication is required; signals use shared market candles.
    algo_meta = ALGORITHMS.get(request.algorithm)
    if not algo_meta:
        raise HTTPException(status_code=404, detail="Algorithm not found")
    if not await stock_by_symbol(request.symbol):
        raise HTTPException(status_code=404, detail="Stock not found")

    interval_map = {"1m": "1 minute", "5m": "5 minutes", "10m": "10 minutes",
                    "15m": "15 minutes", "30m": "30 minutes"}
    interval = interval_map[request.interval]
    rows = await aggregate_candles(request.symbol, int(interval.split()[0]) * 60,
                                   limit=algo_meta["lookback_minutes"], descending=True)
    rows.reverse()
    if len(rows) < algo_meta["lookback_minutes"]:
        raise HTTPException(status_code=422, detail=(f"Need {algo_meta['lookback_minutes']} stored {request.interval} candles; "
                                                       f"found {len(rows)}. Import minute candles or connect a live feed."))

    frame = pd.DataFrame([{"ts": row["_id"], "open": row["open"], "high": row["high"],
                           "low": row["low"], "close": row["close"], "volume": row["volume"]} for row in rows])
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None, run_algo_sync, algo_meta, frame, dict(algo_meta["default_params"])
        )
    except (ValueError, KeyError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail="The selected indicator could not process these candles.") from exc
    latest = rows[-1]["_id"]
    latest_utc = latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else latest.astimezone(timezone.utc)
    age_seconds = max(0, int((datetime.now(timezone.utc) - latest_utc).total_seconds()))
    return {
        "symbol": request.symbol, "algorithm": request.algorithm, "interval": request.interval,
        "as_of": latest_utc.isoformat(), "last_price": float(rows[-1]["close"]),
        "signal": result.model_dump(mode="json"), "candle_count": len(rows),
        "data_age_seconds": age_seconds, "data_status": "recent" if age_seconds <= 2 * int(request.interval[:-1]) * 60 else "stale",
        "data_source": "stored_intraday_candles", "is_live_feed": False,
        "disclaimer": "Indicator signal from stored candles; not a guaranteed outcome or trade instruction.",
    }

@router.post("", response_model=PredictResponse, dependencies=[Depends(RateLimiter(10, 60))])
async def predict_stock(
    request: PredictRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()
    
    if request.algorithm not in ALGORITHMS:
        raise HTTPException(status_code=404, detail="Algorithm not found")
        
    algo_meta = ALGORITHMS[request.algorithm]
    lookback = algo_meta["lookback_minutes"]
    params = dict(algo_meta["default_params"])
    
    # Dashboard date/time selections are wall-clock Eastern Time. Convert a
    # naive timestamp at the API boundary so DST is handled consistently.
    as_of = request.as_of
    if as_of and as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=MARKET_TIMEZONE).astimezone(timezone.utc)
    if as_of:
        market_time = as_of.astimezone(MARKET_TIMEZONE).time()
        if not MARKET_OPEN <= market_time <= MARKET_CLOSE:
            raise HTTPException(status_code=422, detail="Analysis time must be between 07:30 and 13:59 ET.")
    result_as_of = as_of
    
    # 1. Caching logic
    redis = await get_redis_client()
    cache_as_of = str(int(as_of.timestamp())) if as_of else "latest"
    cache_key = f"predict:{request.symbol}:{request.algorithm}:{cache_as_of}:{request.horizon}"
    
    cached = await redis.get(cache_key)
    if cached:
        response.headers["X-Cache"] = "HIT"
        log_prediction(current_user.id, request.symbol, request.algorithm, (time.time() - start_time)*1000, True)
        return json.loads(cached)
        
    response.headers["X-Cache"] = "MISS"
    
    # 2. Fetch Stock
    if not await stock_by_symbol(request.symbol):
        raise HTTPException(status_code=404, detail="Stock not found")
        
    # 3. Fetch Data
    candles = await candles_for_stock(request.symbol, end=as_of, limit=lookback, descending=True)
    
    if len(candles) < lookback:
        raise HTTPException(
            status_code=422, 
            detail=f"Insufficient data. Need {lookback} candles, but found {len(candles)}."
        )
        
    # Order ascending for pandas
    candles.reverse()
    
    if not as_of:
        result_as_of = candles[-1]["ts"]
    
    df = pd.DataFrame([{
        "ts": c["ts"], "open": c["open"], "high": c["high"], "low": c["low"],
        "close": c["close"], "volume": c["volume"]
    } for c in candles])
    
    # 4. Run Algorithm in ThreadPool
    loop = asyncio.get_running_loop()
    try:
        algo_result = await loop.run_in_executor(None, run_algo_sync, algo_meta, df, params)
    except ValueError as exc:
        raise HTTPException(422, "The model could not process this candle data.") from exc
    
    # 5. Build Predicted Candles
    last_close = df['close'].iloc[-1]
    # Simple ATR for volatility
    atr = (df['high'] - df['low']).mean()
    
    # Project based on signal
    direction = 1 if algo_result.signal == "BUY" else (-1 if algo_result.signal == "SELL" else 0)
    
    predicted_candles = []
    current_price = last_close
    current_ts = df['ts'].iloc[-1]
    seed = int.from_bytes(hashlib.sha256(f"{cache_key}:{current_ts}".encode()).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    
    for i in range(request.horizon):
        current_ts = current_ts + pd.Timedelta(minutes=1)
        
        # Add some random walk component bounded by ATR and direction
        step = direction * (atr * 0.1) * algo_result.confidence
        noise = float(rng.normal() * atr * 0.2)
        
        c_open = current_price
        c_close = max(0.01, current_price + step + noise)
        c_high = max(c_open, c_close) + (atr * 0.1)
        c_low = max(0.01, min(c_open, c_close) - (atr * 0.1))
        
        predicted_candles.append({
            "time": int(current_ts.timestamp()),
            "open": float(c_open),
            "high": float(c_high),
            "low": float(c_low),
            "close": float(c_close),
            "volume": 0
        })
        current_price = c_close
        
    history = [CandleAgg(
        time=int(row.ts.timestamp()), open=row.open, high=row.high, low=row.low,
        close=row.close, volume=row.volume
    ) for row in df.itertuples()]
        
    resp_obj = PredictResponse(
        symbol=request.symbol,
        algorithm=request.algorithm,
        as_of=result_as_of,
        lookback_minutes=lookback,
        history=history,
        prediction=algo_result,
        predicted_candles=predicted_candles
    )
    
    resp_dict = resp_obj.model_dump(mode="json")
    
    # Cache logic: 1 hr if fixed as_of, else 60s
    ttl = 3600 if as_of else 60
    await redis.setex(cache_key, ttl, json.dumps(resp_dict, default=str))
    
    log_prediction(current_user.id, request.symbol, request.algorithm, (time.time() - start_time)*1000, False)
    
    return resp_obj
