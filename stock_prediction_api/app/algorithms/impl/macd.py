import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult

class MACDAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        fast = params.get('fast', 12)
        slow = params.get('slow', 26)
        signal_period = params.get('signal', 9)
        
        if len(df) < slow:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()
        histogram = macd_line - signal_line
        
        last_macd = macd_line.iloc[-1]
        last_sig = signal_line.iloc[-1]
        prev_macd = macd_line.iloc[-2]
        prev_sig = signal_line.iloc[-2]
        
        signal = "HOLD"
        reason = "No clear crossover"
        confidence = 0.5
        
        if prev_macd <= prev_sig and last_macd > last_sig:
            signal = "BUY"
            reason = "MACD crossed above signal line"
            confidence = 0.8
        elif prev_macd >= prev_sig and last_macd < last_sig:
            signal = "SELL"
            reason = "MACD crossed below signal line"
            confidence = 0.8
        elif last_macd > last_sig:
            signal = "BUY"
            reason = "MACD is bullish"
            confidence = 0.6
        elif last_macd < last_sig:
            signal = "SELL"
            reason = "MACD is bearish"
            confidence = 0.6
            
        recent_macd = macd_line.tail(60)
        recent_sig = signal_line.tail(60)
        recent_hist = histogram.tail(60)
        
        overlays = {
            "macd": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_macd.index, recent_macd.values)],
            "signal": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_sig.index, recent_sig.values)],
            "histogram": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_hist.index, recent_hist.values)],
        }
        
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, overlays=overlays)
