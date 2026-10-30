from datetime import datetime, timedelta, timezone

from app.models.stock import Stock
from app.models.candle import Candle
from app.core.redis import get_redis_client


async def test_intraday_candles_prediction_and_cache(client, db_session):
    await client.post("/auth/register", json={"email": "intraday@example.com", "name": "Intraday", "password": "password123"})
    login = await client.post("/auth/login", json={"email": "intraday@example.com", "password": "password123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    stock = Stock(symbol="TEST_INTRADAY", name="Test candles", exchange="NYSE")
    db_session.add(stock)
    await db_session.flush()
    start = datetime(2024, 1, 2, 14, 30, tzinfo=timezone.utc)
    for index in range(120):
        close = 100 + index * 0.05
        db_session.add(Candle(stock_id=stock.id, ts=start + timedelta(minutes=index),
                              open=close - 0.02, high=close + 0.1, low=close - 0.1, close=close, volume=100))
    await db_session.commit()
    candles = await client.get("/app/stocks/TEST_INTRADAY/candles", headers=headers, params={"interval": "5m"})
    assert candles.status_code == 200
    assert len(candles.json()) == 24
    assert all(candle["volume"] == 500 for candle in candles.json())
    payload = {"symbol": stock.symbol, "algorithm": "rsi", "as_of": "2024-01-02T11:29:00-05:00", "horizon": 5}
    first = await client.post("/app/predict", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert len(first.json()["predicted_candles"]) == 5
    cached = await client.post("/app/predict", headers=headers, json=payload)
    assert cached.headers["X-Cache"] == "HIT"
    assert cached.json() == first.json()
    redis = await get_redis_client()
    key = f"predict:TEST_INTRADAY:rsi:{int(datetime(2024, 1, 2, 16, 29, tzinfo=timezone.utc).timestamp())}:5"
    await redis.delete(key)
    rerun = await client.post("/app/predict", headers=headers, json=payload)
    assert rerun.headers["X-Cache"] == "MISS"
    assert rerun.json() == first.json()
