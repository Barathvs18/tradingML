import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult, Marker

class HammerAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        if len(df) < 5:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        
        # Hammer definition: small body, long lower shadow, very little upper shadow
        # Occurs in a downtrend (we'll just detect the shape for now)
        
        df['body'] = abs(df['close'] - df['open'])
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        
        # Lower shadow at least twice the real body
        # Upper shadow very small (less than 10% of total range)
        df['range'] = df['high'] - df['low']
        
        df['hammer'] = (
            (df['lower_shadow'] >= (2.0 * df['body'])) & 
            (df['upper_shadow'] <= (0.1 * df['range'])) &
            (df['body'] > 0)
        )
        
        markers = []
        recent = df.tail(self.lookback_minutes)
        
        for idx, row in recent.iterrows():
            if row['hammer']:
                markers.append(Marker(
                    time=int(row.ts.timestamp()),
                    position="belowBar",
                    label="Hammer"
                ))
                
        last_is_hammer = df['hammer'].iloc[-1]
        
        signal = "HOLD"
        reason = "No Hammer pattern detected on latest candle"
        confidence = 0.5
        
        if last_is_hammer:
            signal = "BUY"
            reason = "Hammer pattern detected (Bullish Reversal)"
            confidence = 0.75
            
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, markers=markers)
