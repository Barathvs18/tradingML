from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.algorithms.base import AlgoResult
from app.schemas.app import CandleAgg

class PredictRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_&.-]+$")
    algorithm: str = Field(min_length=1, max_length=64)
    as_of: Optional[datetime] = None
    horizon: int = Field(default=15, ge=1, le=240, description="Forecast duration in minutes")

class IntradayPredictRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_&.-]+$")
    algorithm: str = Field(min_length=1, max_length=64)
    interval: str = Field(default="5m", pattern=r"^(1m|5m|10m|15m|30m)$")

class PredictResponse(BaseModel):
    symbol: str
    algorithm: str
    as_of: datetime
    lookback_minutes: int
    history: List[CandleAgg]
    prediction: AlgoResult
    predicted_candles: List[CandleAgg]
    disclaimer: str = "Future candles are a reproducible simulation, not model-predicted prices. Historical research only."
