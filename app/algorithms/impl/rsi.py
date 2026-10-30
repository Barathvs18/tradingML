import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult

class RSIAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        period = params.get('period', 14)
        if len(df) < period:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/period, adjust=False).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        last_rsi = rsi.iloc[-1]
        prev_rsi = rsi.iloc[-2]
        
        signal = "HOLD"
        reason = f"RSI is neutral ({last_rsi:.1f})"
        confidence = 0.5
        
        if last_rsi < 30:
            signal = "BUY"
            reason = f"RSI is oversold ({last_rsi:.1f})"
            confidence = 0.8
        elif last_rsi > 70:
            signal = "SELL"
            reason = f"RSI is overbought ({last_rsi:.1f})"
            confidence = 0.8
            
        # Crossover logic
        if prev_rsi < 30 and last_rsi >= 30:
            signal = "BUY"
            reason = "RSI crossed back above 30"
            confidence = 0.9
        elif prev_rsi > 70 and last_rsi <= 70:
            signal = "SELL"
            reason = "RSI crossed back below 70"
            confidence = 0.9
            
        recent_rsi = rsi.tail(60)
        overlays = {
            "rsi": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_rsi.index, recent_rsi.values)]
        }
        
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, overlays=overlays)
