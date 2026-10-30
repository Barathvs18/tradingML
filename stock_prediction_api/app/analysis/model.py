"""Daily direction model: causal features, a chronological holdout, JSON inference."""

import hashlib
import io
import json

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

DIRECTIONS = ["DOWN", "SIDEWAYS", "UP"]
THRESHOLD = 0.005
FEATURES = ["return_1", "return_5", "return_20", "ma_5_distance", "ma_20_distance",
            "rsi_14", "atr_14_pct", "volatility_20", "volume_ratio_20", "opening_gap", "body_return"]
MODEL_REVISION = "daily-logit-v1"


def read_daily_csv(raw: bytes) -> pd.DataFrame:
    if len(raw) > 4_000_000:
        raise ValueError("CSV must be smaller than 4 MB.")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise ValueError("Could not read the CSV. Upload a UTF-8 daily OHLCV file.") from exc
    df.columns = [str(column).strip().lower() for column in df.columns]
    if df.columns.duplicated().any():
        raise ValueError("CSV contains duplicate column names.")
    required = ["date", "open", "high", "low", "close", "volume"]
    if not set(required).issubset(df.columns):
        raise ValueError("Required CSV columns: date, open, high, low, close, volume.")
    df = df[required].copy()
    if not 300 <= len(df) <= 20000:
        raise ValueError("Upload between 300 and 20,000 daily candles.")
    if not df["date"].astype(str).str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
        raise ValueError("Dates must use YYYY-MM-DD. This version accepts daily candles only.")
    dates = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")
    if dates.isna().any() or dates.duplicated().any():
        raise ValueError("CSV contains invalid or duplicate trading dates.")
    for column in required[1:]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if not np.isfinite(df[required[1:]].to_numpy()).all():
        raise ValueError("Prices and volume must contain finite numeric values.")
    invalid = ((df[["open", "high", "low", "close"]] <= 0).any(axis=1)
               | (df["high"] < df[["open", "close", "low"]].max(axis=1))
               | (df["low"] > df[["open", "close", "high"]].min(axis=1))
               | (df["volume"] < 0) | (df["volume"] % 1 != 0))
    if invalid.any():
        raise ValueError(f"CSV contains {int(invalid.sum())} invalid OHLCV rows.")
    df["date"] = dates.dt.strftime("%Y-%m-%d")
    return df.sort_values("date").reset_index(drop=True)


def features(df: pd.DataFrame) -> pd.DataFrame:
    """Every feature uses only the current candle and earlier candles."""
    close = df["close"]
    returns = close.pct_change(fill_method=None)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    rsi = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    rsi = rsi.mask((loss == 0) & (gain > 0), 100).mask((loss == 0) & (gain == 0), 50)
    true_range = pd.concat([df["high"] - df["low"], (df["high"] - close.shift()).abs(),
                            (df["low"] - close.shift()).abs()], axis=1).max(axis=1)
    result = pd.DataFrame({
        "return_1": returns,
        "return_5": close.pct_change(5, fill_method=None),
        "return_20": close.pct_change(20, fill_method=None),
        "ma_5_distance": close / close.rolling(5).mean() - 1,
        "ma_20_distance": close / close.rolling(20).mean() - 1,
        "rsi_14": rsi,
        "atr_14_pct": true_range.ewm(alpha=1 / 14, adjust=False).mean() / close,
        "volatility_20": returns.rolling(20).std(),
        "volume_ratio_20": df["volume"] / df["volume"].rolling(20).mean().replace(0, np.nan),
        "opening_gap": df["open"] / close.shift() - 1,
        "body_return": close / df["open"] - 1,
    })
    result["volume_ratio_20"] = result["volume_ratio_20"].fillna(1.0)
    return result.replace([np.inf, -np.inf], np.nan)


def direction(value: float, threshold: float = THRESHOLD) -> str:
    return "UP" if value > threshold else "DOWN" if value < -threshold else "SIDEWAYS"


def train(df: pd.DataFrame) -> dict:
    matrix = features(df)
    next_returns = df["close"].shift(-1) / df["close"] - 1
    usable = matrix.notna().all(axis=1) & next_returns.notna()
    indices = df.index[usable].to_numpy()
    boundary = int(len(indices) * 0.7)
    # Omit one sample between training and testing. Its target would overlap
    # the first held-out candle. No scaler or model is fitted on holdout data.
    train_indices = indices[:boundary - 1]
    test_indices = indices[boundary:]
    labels = next_returns.map(lambda value: direction(value) if pd.notna(value) else None)
    train_y = labels.loc[train_indices]
    if len(train_indices) < 150 or len(test_indices) < 50:
        raise ValueError("Not enough usable candles after indicator warm-up.")
    counts = train_y.value_counts()
    if any(counts.get(label, 0) < 5 for label in DIRECTIONS):
        raise ValueError("Training data needs at least five UP, DOWN and SIDEWAYS examples each.")
    pipeline = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=1500, random_state=42))
    pipeline.fit(matrix.loc[train_indices, FEATURES], train_y)
    predicted = pipeline.predict(matrix.loc[test_indices, FEATURES])
    actual = labels.loc[test_indices]
    majority = str(train_y.value_counts().idxmax())
    precision, recall, f1, support = precision_recall_fscore_support(actual, predicted, labels=DIRECTIONS, zero_division=0)
    scaler, classifier = pipeline.steps[0][1], pipeline.steps[1][1]
    digest = hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()
    report = {
        "accuracy": float(accuracy_score(actual, predicted)),
        "macro_f1": float(f1_score(actual, predicted, labels=DIRECTIONS, average="macro", zero_division=0)),
        "baseline_accuracy": float(accuracy_score(actual, [majority] * len(actual))),
        "baseline_class": majority,
        "confusion_matrix": confusion_matrix(actual, predicted, labels=DIRECTIONS).tolist(),
        "classes": DIRECTIONS,
        "per_class": [{"direction": label, "precision": float(precision[i]), "recall": float(recall[i]),
                       "f1": float(f1[i]), "support": int(support[i])} for i, label in enumerate(DIRECTIONS)],
        "training_samples": len(train_indices), "test_samples": len(test_indices), "gap_samples": 1,
        "training_start": str(df.loc[train_indices[0], "date"]),
        "training_end": str(df.loc[train_indices[-1], "date"]),
        "training_outcomes_end": str(df.loc[train_indices[-1] + 1, "date"]),
        "test_start": str(df.loc[test_indices[0], "date"]),
        "test_end": str(df.loc[test_indices[-1], "date"]),
        "large_move_days": int((next_returns.abs() > 0.15).sum()),
    }
    return {"version": f"{MODEL_REVISION}-{digest[:16]}", "feature_names": FEATURES, "threshold": THRESHOLD,
            "classes": classifier.classes_.tolist(), "mean": scaler.mean_.tolist(), "scale": scaler.scale_.tolist(),
            "coefficients": classifier.coef_.tolist(), "intercepts": classifier.intercept_.tolist(),
            "report": report, "dataset_sha256": digest}


def predict(model: dict, row: pd.Series) -> dict:
    values = row[model["feature_names"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Not enough prior candles to calculate the model inputs.")
    scaled = (values - np.asarray(model["mean"])) / np.asarray(model["scale"])
    scores = np.asarray(model["coefficients"]) @ scaled + np.asarray(model["intercepts"])
    exponentials = np.exp(scores - scores.max())
    probabilities = exponentials / exponentials.sum()
    mapped = {label: float(probability) for label, probability in zip(model["classes"], probabilities)}
    return {"direction": max(mapped, key=mapped.get), "probabilities": mapped}


def canonical_json(value) -> str:
    return json.dumps(value, allow_nan=False, separators=(",", ":"))
