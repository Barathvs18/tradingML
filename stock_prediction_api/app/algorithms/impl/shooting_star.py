import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult, Marker

class ShootingStarAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        if len(df) < 5:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        
        # Shooting Star definition: small body, long upper shadow, very little lower shadow
        
        df['body'] = abs(df['close'] - df['open'])
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        
        df['range'] = df['high'] - df['low']
        
        df['shooting_star'] = (
            (df['upper_shadow'] >= (2.0 * df['body'])) & 
            (df['lower_shadow'] <= (0.1 * df['range'])) &
            (df['body'] > 0)
        )
        
        markers = []
        recent = df.tail(self.lookback_minutes)
        
        for idx, row in recent.iterrows():
            if row['shooting_star']:
                markers.append(Marker(
                    time=int(row.ts.timestamp()),
                    position="aboveBar",
                    label="Shooting Star"
                ))
                
        last_is_shooting_star = df['shooting_star'].iloc[-1]
        
        signal = "HOLD"
        reason = "No Shooting Star pattern detected on latest candle"
        confidence = 0.5
        
        if last_is_shooting_star:
            signal = "SELL"
            reason = "Shooting Star pattern detected (Bearish Reversal)"
            confidence = 0.75
            
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, markers=markers)
