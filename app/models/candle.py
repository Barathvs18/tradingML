from dataclasses import dataclass
from datetime import datetime

@dataclass
class Candle:
    stock_id: str
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
