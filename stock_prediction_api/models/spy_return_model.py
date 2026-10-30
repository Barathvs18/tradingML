"""Runtime adapter for the model created by scripts/train_return_model.py."""

import json
from pathlib import Path

from app.algorithms.base import AlgoResult


_MODEL = None


def _model():
    global _MODEL
    if _MODEL is None:
        path = Path(__file__).with_name("spy_return_model.json")
        if not path.exists():
            raise RuntimeError("SPY model has not been trained. Run scripts/train_return_model.py first.")
        _MODEL = json.loads(path.read_text(encoding="utf-8"))
    return _MODEL


def main(df):
    """Predict the next one-minute return from the latest OHLCV candle."""
    if len(df) < 2:
        return AlgoResult(signal="HOLD", confidence=0.0, reason="Need at least two candles.", overlays={}, markers=[])

    model = _model()
    previous = df.iloc[-2]
    latest = df.iloc[-1]
    features = [
        latest["close"] / previous["close"] - 1.0,
        latest["high"] / latest["low"] - 1.0,
        latest["close"] / latest["open"] - 1.0,
        latest["volume"] / max(previous["volume"], 1) - 1.0,
    ]
    features = [max(-0.1, min(0.1, float(value))) for value in features]
    predicted_return = model["intercept"] + sum(weight * value for weight, value in zip(model["coefficients"], features))
    threshold = model["signal_threshold"]
    signal = "BUY" if predicted_return > threshold else "SELL" if predicted_return < -threshold else "HOLD"
    confidence = min(0.95, 0.5 + abs(predicted_return) / max(threshold * 8, 1e-9))
    return AlgoResult(
        signal=signal,
        confidence=round(confidence, 3),
        reason=f"Linear next-minute return forecast: {predicted_return:.5%}",
        overlays={},
        markers=[],
    )
