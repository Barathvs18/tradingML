import pandas as pd
import numpy as np
from app.algorithms.base import BaseAlgorithm, AlgoResult

class ADXAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        period = params.get('period', 14)
        if len(df) < period * 2:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        
        df['+dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['-dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        atr = df['tr'].rolling(period).sum() # Simplified RMA approximation for first value
        atr = df['tr'].ewm(alpha=1/period, adjust=False).mean()
        
        plus_di = 100 * (df['+dm'].ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (df['-dm'].ewm(alpha=1/period, adjust=False).mean() / atr)
        
        dx = 100 * (abs(plus_di - minus_di) / (plus_di + minus_di))
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        last_adx = adx.iloc[-1]
        last_plus = plus_di.iloc[-1]
        last_minus = minus_di.iloc[-1]
        
        signal = "HOLD"
        confidence = 0.5
        reason = "Trend is weak"
        
        if last_adx > 25:
            confidence = min(0.5 + (last_adx / 100.0), 1.0)
            if last_plus > last_minus:
                signal = "BUY"
                reason = f"Strong Uptrend (ADX: {last_adx:.1f})"
            elif last_minus > last_plus:
                signal = "SELL"
                reason = f"Strong Downtrend (ADX: {last_adx:.1f})"
                
        recent_adx = adx.tail(60)
        overlays = {
            "adx": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_adx.index, recent_adx.values)]
        }
        
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, overlays=overlays)
