import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult

class ATRAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        period = params.get('period', 14)
        if len(df) < period:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        atr = df['tr'].ewm(span=period, adjust=False).mean()
        
        last_atr = atr.iloc[-1]
        
        # ATR is a volatility indicator, rarely used for standalone directional signals
        signal = "HOLD"
        reason = f"Volatility (ATR) is {last_atr:.2f}"
        
        recent_atr = atr.tail(60)
        overlays = {
            "atr": [{"time": int(df['ts'].iloc[i].timestamp()), "value": float(v)} for i, v in zip(recent_atr.index, recent_atr.values)]
        }
        
        return AlgoResult(signal=signal, confidence=0.5, reason=reason, overlays=overlays)
