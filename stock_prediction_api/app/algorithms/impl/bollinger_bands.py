import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult

class BollingerBandsAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        period = params.get('period', 20)
        std_dev = params.get('std_dev', 2.0)
        
        if len(df) < period:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper_band = sma + (std_dev * std)
        lower_band = sma - (std_dev * std)
        
        last_close = df['close'].iloc[-1]
        last_upper = upper_band.iloc[-1]
        last_lower = lower_band.iloc[-1]
        
        signal = "HOLD"
        reason = "Price within bands"
        confidence = 0.5
        
        if last_close > last_upper:
            signal = "SELL"
            reason = "Price above upper band (Overbought)"
            confidence = 0.7
        elif last_close < last_lower:
            signal = "BUY"
            reason = "Price below lower band (Oversold)"
            confidence = 0.7
            
        recent_upper = upper_band.tail(60)
        recent_lower = lower_band.tail(60)
        
        overlays = {
            "upper_band": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_upper.index, recent_upper.values)],
            "lower_band": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_lower.index, recent_lower.values)],
        }
        
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, overlays=overlays)
