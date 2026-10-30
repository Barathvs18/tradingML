import asyncio
import time
import threading
from collections import defaultdict, deque
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Header, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal

from app.analysis.store import AnalysisStore, get_store

router = APIRouter(prefix="/analysis", tags=["Indian stock analysis"])
stream_router = APIRouter(tags=["Historical candle stream"])


def analysis_owner() -> str:
    """Local app identity. The full app overrides this with the authenticated user."""
    return "local"


def analysis_limit():
    """The authenticated server overrides this with Redis request limits."""
    return None


router.dependencies.append(Depends(analysis_limit))
_public_calls = defaultdict(deque)
_public_calls_lock = threading.Lock()


def enforce_public_api_limit(owner: str):
    now = time.monotonic()
    with _public_calls_lock:
        calls = _public_calls[owner]
        while calls and calls[0] <= now - 60:
            calls.popleft()
        if len(calls) >= 60:
            raise HTTPException(status_code=429, detail="Public API limit reached; retry in one minute.",
                                headers={"Retry-After": "60"})
        calls.append(now)


class AnalyzeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20)
    as_of: date


class StrategyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    symbol: str = Field(min_length=1, max_length=20)
    strategy_type: Literal["sma_crossover", "rsi_reversion", "rule_chain"]
    parameters: dict[str, Any] = Field(max_length=6)
    initial_capital: float = Field(ge=1000, le=1_000_000_000)
    transaction_cost_bps: float = Field(ge=0, le=100)


class PaperOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=20)
    as_of: date
    side: Literal["BUY", "SELL"]
    order_type: Literal["market", "limit", "stop_loss", "take_profit"]
    quantity: int = Field(ge=1, le=1_000_000)
    trigger_price: float | None = Field(default=None, gt=0)


class LeaderboardPreference(BaseModel):
    enabled: bool


class PublishPreference(BaseModel):
    published: bool = True


class AutomationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    strategy_id: str = Field(min_length=1, max_length=80)
    interval_minutes: int = Field(ge=1, le=1440)
    quantity: int = Field(ge=1, le=1_000_000)
    auto_trade: bool = False


class AutomationEnabledRequest(BaseModel):
    enabled: bool


class AlertWebhookRequest(BaseModel):
    webhook_url: str = Field(min_length=20, max_length=2000)


async def run(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc), headers={"Retry-After": "5"}) from exc


@router.get("/stocks")
async def stocks(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.stocks, owner)


@router.get("/stocks/{symbol}/dates")
async def dates(symbol: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.dates, owner, symbol)


@router.post("/predict")
async def analyze(payload: AnalyzeRequest, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.analyze, owner, payload.symbol, payload.as_of.isoformat())


@router.get("/history")
async def history(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.history, owner)


@router.post("/history/{prediction_id}/reveal")
async def reveal(prediction_id: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.reveal, owner, prediction_id)


@router.get("/stocks/{symbol}/performance")
async def performance(symbol: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.performance, owner, symbol)


@router.get("/stocks/{symbol}/compare")
async def compare_algorithms(symbol: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.compare_algorithms, owner, symbol)


@router.post("/import")
async def import_csv(request: Request, symbol: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > 4_000_000:
            raise HTTPException(status_code=413, detail="CSV must be smaller than 4 MB.")
        chunks.append(chunk)
    return await run(store.import_csv, symbol, b"".join(chunks), owner)


@router.get("/strategies")
async def strategies(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.strategies, owner)


@router.post("/strategies")
async def create_strategy(payload: StrategyCreateRequest, owner: str = Depends(analysis_owner),
                          store: AnalysisStore = Depends(get_store)):
    return await run(store.create_strategy, owner, payload.model_dump())


@router.delete("/strategies/{strategy_id}")
async def delete_strategy(strategy_id: str, owner: str = Depends(analysis_owner),
                          store: AnalysisStore = Depends(get_store)):
    return await run(store.delete_strategy, owner, strategy_id)


@router.post("/strategies/{strategy_id}/backtest")
async def backtest_strategy(strategy_id: str, owner: str = Depends(analysis_owner),
                            store: AnalysisStore = Depends(get_store)):
    return await run(store.backtest_strategy, owner, strategy_id)


@router.put("/strategies/{strategy_id}/publish")
async def publish_strategy(strategy_id: str, payload: PublishPreference,
                           owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.publish_strategy, owner, strategy_id, payload.published)


@router.get("/marketplace")
async def marketplace(store: AnalysisStore = Depends(get_store)):
    return await run(store.marketplace_strategies)


@router.post("/marketplace/{strategy_id}/clone")
async def clone_strategy(strategy_id: str, owner: str = Depends(analysis_owner),
                          store: AnalysisStore = Depends(get_store)):
    return await run(store.clone_strategy, owner, strategy_id)


@router.get("/paper")
async def paper_account(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.paper_account, owner)


@router.get("/paper/stocks/{symbol}/dates")
async def paper_dates(symbol: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.paper_dates, owner, symbol)


@router.post("/paper/orders")
async def place_paper_order(payload: PaperOrderRequest, owner: str = Depends(analysis_owner),
                            store: AnalysisStore = Depends(get_store)):
    return await run(store.place_paper_order, owner, payload.model_dump())


@router.post("/paper/orders/{order_id}/process")
async def process_paper_order(order_id: str, as_of: date, owner: str = Depends(analysis_owner),
                              store: AnalysisStore = Depends(get_store)):
    return await run(store.process_paper_order, owner, order_id, as_of.isoformat())


@router.delete("/paper/orders/{order_id}")
async def cancel_paper_order(order_id: str, owner: str = Depends(analysis_owner),
                             store: AnalysisStore = Depends(get_store)):
    return await run(store.cancel_paper_order, owner, order_id)


@router.put("/paper/leaderboard-preference")
async def leaderboard_preference(payload: LeaderboardPreference, owner: str = Depends(analysis_owner),
                                 store: AnalysisStore = Depends(get_store)):
    return await run(store.set_leaderboard_opt_in, owner, payload.enabled)


@router.get("/leaderboard")
async def leaderboard(store: AnalysisStore = Depends(get_store)):
    return await run(store.paper_leaderboard)


@router.get("/automations")
async def automations(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.automations, owner)


@router.post("/automations")
async def create_automation(payload: AutomationCreateRequest, owner: str = Depends(analysis_owner),
                            store: AnalysisStore = Depends(get_store)):
    return await run(store.create_automation, owner, payload.model_dump())


@router.put("/automations/{automation_id}")
async def set_automation(automation_id: str, payload: AutomationEnabledRequest,
                         owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.set_automation_enabled, owner, automation_id, payload.enabled)


@router.delete("/automations/{automation_id}")
async def delete_automation(automation_id: str, owner: str = Depends(analysis_owner),
                            store: AnalysisStore = Depends(get_store)):
    return await run(store.delete_automation, owner, automation_id)


@router.get("/alerts")
async def alerts(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.alerts, owner)


@router.put("/alerts/{alert_id}/read")
async def read_alert(alert_id: str, owner: str = Depends(analysis_owner),
                     store: AnalysisStore = Depends(get_store)):
    return await run(store.mark_alert_read, owner, alert_id)


@router.get("/alerts/webhook")
async def alert_webhook_status(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.alert_webhook_status, owner)


@router.put("/alerts/webhook")
async def set_alert_webhook(payload: AlertWebhookRequest, owner: str = Depends(analysis_owner),
                            store: AnalysisStore = Depends(get_store)):
    return await run(store.set_alert_webhook, owner, payload.webhook_url)


@router.delete("/alerts/webhook")
async def remove_alert_webhook(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.remove_alert_webhook, owner)


@router.post("/api-keys")
async def create_api_key(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.create_public_api_key, owner)


@router.get("/api-keys")
async def api_keys(owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.public_api_keys, owner)


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(key_id: str, owner: str = Depends(analysis_owner), store: AnalysisStore = Depends(get_store)):
    return await run(store.revoke_public_api_key, owner, key_id)


@router.post("/public/v1/predict")
async def public_predict(payload: AnalyzeRequest, x_api_key: str = Header(min_length=8, max_length=128),
                         store: AnalysisStore = Depends(get_store)):
    owner = await run(store.public_api_key_owner, x_api_key)
    if owner is None:
        raise HTTPException(status_code=401, detail="A valid X-API-Key header is required.")
    enforce_public_api_limit(owner)
    result = await run(store.analyze, owner, payload.symbol, payload.as_of.isoformat())
    return {"symbol": result["symbol"], "as_of": result["as_of"], "direction": result["direction"],
            "probabilities": result["probabilities"], "model_version": result["model_version"],
            "data_horizon": "Historical daily data through 2021-04-30"}


@stream_router.websocket("/stream/{symbol}")
async def historical_stream(websocket: WebSocket, symbol: str,
                            speed_ms: int = Query(default=1000, ge=200, le=30000),
                            limit: int = Query(default=250, ge=1, le=1000),
                            from_date: date | None = None,
                            store: AnalysisStore = Depends(get_store)):
    await websocket.accept()
    try:
        candles = await asyncio.to_thread(store.stream_candles, symbol, limit,
                                          from_date.isoformat() if from_date else None)
        for index, candle in enumerate(candles):
            await websocket.send_json({"type": "candle", "symbol": symbol, "sequence": index + 1,
                                       "total": len(candles), "candle": candle})
            if index + 1 < len(candles):
                await asyncio.sleep(speed_ms / 1000)
        await websocket.send_json({"type": "complete", "symbol": symbol, "total": len(candles)})
    except LookupError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass
