from abc import ABC, abstractmethod
import pandas as pd
from pydantic import BaseModel
from typing import Dict, List, Optional, Any

class Marker(BaseModel):
    time: int
    position: str  # e.g., 'aboveBar', 'belowBar'
    label: str

class AlgoResult(BaseModel):
    signal: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0.0 to 1.0
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    overlays: Dict[str, List[Dict[str, Any]]] = {}  # e.g., {"rsi": [{"time": 123, "value": 45}]}
    markers: List[Marker] = []
    reason: str

class BaseAlgorithm(ABC):
    key: str
    lookback_minutes: int
    
    def __init__(self, key: str, lookback_minutes: int):
        self.key = key
        self.lookback_minutes = lookback_minutes
        
    @abstractmethod
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        """
        Executes the algorithm on a DataFrame of 1-minute candles.
        Expected columns: ts, open, high, low, close, volume (ascending time).
        """
        pass
