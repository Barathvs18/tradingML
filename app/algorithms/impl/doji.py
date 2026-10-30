import pandas as pd
from app.algorithms.base import BaseAlgorithm, AlgoResult, Marker

class DojiAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        if len(df) < 5:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        
        # Compare the body with the recent high-low range. Using candle bodies here
        # makes a run of equally small bodies impossible to classify as a Doji.
        avg_candle_size = (df["high"] - df["low"]).rolling(5).median()
        
        # Doji condition: close to open is very small compared to average candle
        df["doji"] = abs(df["close"] - df["open"]) <= (0.05 * avg_candle_size)
        
        markers = []
        recent = df.tail(self.lookback_minutes)
        
        for idx, row in recent.iterrows():
            if row['doji']:
                markers.append(Marker(
                    time=int(row.ts.timestamp()),
                    position="aboveBar",
                    label="Doji"
                ))
                
        last_is_doji = df['doji'].iloc[-1]
        
        signal = "HOLD"
        reason = "No Doji pattern detected on latest candle"
        confidence = 0.5
        
        if last_is_doji:
            reason = "Doji pattern detected (Indecision/Reversal)"
            # Doji alone doesn't give direction without context, but signals potential reversal
            confidence = 0.7
            
        return AlgoResult(signal=signal, confidence=confidence, reason=reason, markers=markers)
