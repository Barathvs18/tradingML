import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult

class PivotPointsAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        if len(df) < 1:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        # We need the previous day's High, Low, Close to calculate today's pivots.
        # Since we just get 1-minute candles, we'll approximate the daily pivot 
        # by taking the max high, min low, and last close of the dataset (assuming it represents the previous day).
        
        # In a real setup, we should resample to daily.
        prev_high = df['high'].max()
        prev_low = df['low'].min()
        prev_close = df['close'].iloc[-1]
        
        pivot = (prev_high + prev_low + prev_close) / 3
        r1 = (2 * pivot) - prev_low
        s1 = (2 * pivot) - prev_high
        
        last_close = df['close'].iloc[-1]
        
        signal = "HOLD"
        reason = f"Price ({last_close:.2f}) near Pivot ({pivot:.2f})"
        confidence = 0.5
        
        if last_close > r1:
            signal = "SELL"
            reason = f"Price above R1 ({r1:.2f}) - Overextended"
        elif last_close < s1:
            signal = "BUY"
            reason = f"Price below S1 ({s1:.2f}) - Oversold"
        elif last_close > pivot:
            signal = "BUY"
            reason = f"Price above Pivot ({pivot:.2f}) - Bullish"
        elif last_close < pivot:
            signal = "SELL"
            reason = f"Price below Pivot ({pivot:.2f}) - Bearish"
            
        # Create horizontal lines for the recent timeframe
        recent = df.tail(60)
        overlays = {
            "pivot": [{"time": int(r.ts.timestamp()), "value": float(pivot)} for r in recent.itertuples()],
            "r1": [{"time": int(r.ts.timestamp()), "value": float(r1)} for r in recent.itertuples()],
            "s1": [{"time": int(r.ts.timestamp()), "value": float(s1)} for r in recent.itertuples()]
        }
        
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, overlays=overlays)
