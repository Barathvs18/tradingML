import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult, Marker

class MarubozuAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        if len(df) < 5:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        
        # Marubozu definition: body is almost the entire range
        
        df['body'] = abs(df['close'] - df['open'])
        df['range'] = df['high'] - df['low']
        
        # Body is at least 95% of the range
        df['marubozu'] = df['body'] >= (0.95 * df['range'])
        df['bullish'] = df['close'] > df['open']
        
        markers = []
        recent = df.tail(self.lookback_minutes)
        
        for idx, row in recent.iterrows():
            if row['marubozu']:
                color = "Bullish" if row['bullish'] else "Bearish"
                markers.append(Marker(
                    time=int(row.ts.timestamp()),
                    position="aboveBar" if not row['bullish'] else "belowBar",
                    label=f"{color} Marubozu"
                ))
                
        last_row = df.iloc[-1]
        
        signal = "HOLD"
        reason = "No Marubozu pattern detected on latest candle"
        confidence = 0.5
        
        if last_row['marubozu']:
            if last_row['bullish']:
                signal = "BUY"
                reason = "Bullish Marubozu (Strong Momentum)"
                confidence = 0.8
            else:
                signal = "SELL"
                reason = "Bearish Marubozu (Strong Momentum)"
                confidence = 0.8
            
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, markers=markers)
