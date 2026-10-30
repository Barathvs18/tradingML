import pandas as pd
import numpy as np
from app.algorithms.base import BaseAlgorithm, AlgoResult

class SuperTrendAlgo(BaseAlgorithm):
    def __init__(self, key: str, lookback_minutes: int):
        super().__init__(key, lookback_minutes)
        
    def run(self, df: pd.DataFrame, params: dict) -> AlgoResult:
        period = params.get('period', 7)
        multiplier = params.get('multiplier', 3.0)
        
        if len(df) < period:
            return AlgoResult(signal="HOLD", confidence=0.0, reason="Not enough data")
            
        df = df.copy()
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].ewm(span=period, adjust=False).mean()
        
        hl2 = (df['high'] + df['low']) / 2
        df['upperband'] = hl2 + (multiplier * df['atr'])
        df['lowerband'] = hl2 - (multiplier * df['atr'])
        df['in_uptrend'] = True
        
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['upperband'].iloc[i-1]:
                df.iloc[i, df.columns.get_loc('in_uptrend')] = True
            elif df['close'].iloc[i] < df['lowerband'].iloc[i-1]:
                df.iloc[i, df.columns.get_loc('in_uptrend')] = False
            else:
                df.iloc[i, df.columns.get_loc('in_uptrend')] = df.iloc[i-1, df.columns.get_loc('in_uptrend')]
                if df['in_uptrend'].iloc[i] and df['lowerband'].iloc[i] < df['lowerband'].iloc[i-1]:
                    df.iloc[i, df.columns.get_loc('lowerband')] = df.iloc[i-1, df.columns.get_loc('lowerband')]
                if not df['in_uptrend'].iloc[i] and df['upperband'].iloc[i] > df['upperband'].iloc[i-1]:
                    df.iloc[i, df.columns.get_loc('upperband')] = df.iloc[i-1, df.columns.get_loc('upperband')]
                    
        df['supertrend'] = np.where(df['in_uptrend'], df['lowerband'], df['upperband'])
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        signal = "HOLD"
        reason = "Trend is stable"
        if not prev_row['in_uptrend'] and last_row['in_uptrend']:
            signal = "BUY"
            reason = "Price crossed above Supertrend"
        elif prev_row['in_uptrend'] and not last_row['in_uptrend']:
            signal = "SELL"
            reason = "Price crossed below Supertrend"
        elif last_row['in_uptrend']:
            signal = "BUY"
            reason = "In Uptrend"
        else:
            signal = "SELL"
            reason = "In Downtrend"
            
        overlay_st = [{"time": int(r.ts.timestamp()), "value": float(r.supertrend)} for r in df.tail(60).itertuples()]
        
        return AlgoResult(
            signal=signal,
            confidence=0.8,
            target_price=last_row['close'] * 1.02 if signal == "BUY" else last_row['close'] * 0.98,
            stop_loss=float(last_row['supertrend']),
            reason=reason,
            overlays={"supertrend": overlay_st}
        )
