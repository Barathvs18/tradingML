import pandas as pd
import numpy as np
from app.algorithms.base import BaseAlgorithm, AlgoResult

class LinearRegressionSlopeAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        period = params.get('period', 14)
        if len(df) < period:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        y = df['close'].tail(period).values
        x = np.arange(period)
        
        # Calculate slope
        slope, intercept = np.polyfit(x, y, 1)
        
        signal = "HOLD"
        confidence = 0.5
        reason = f"Slope is flat ({slope:.4f})"
        
        if slope > 0.05:
            signal = "BUY"
            confidence = min(0.5 + (slope * 5), 1.0)
            reason = f"Positive slope ({slope:.4f})"
        elif slope < -0.05:
            signal = "SELL"
            confidence = min(0.5 + (abs(slope) * 5), 1.0)
            reason = f"Negative slope ({slope:.4f})"
            
        # Add regression line to overlays
        last_n = df.tail(period)
        reg_line = []
        for i, row in enumerate(last_n.itertuples()):
            reg_line.append({"time": int(row.ts.timestamp()), "value": intercept + slope * i})
            
        return AlgoResult(
            signal=signal,
            confidence=confidence,
            reason=reason,
            overlays={"regression_line": reg_line}
        )
