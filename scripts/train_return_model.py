"""Train a lightweight, reproducible SPY next-minute return model using NumPy only."""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


FEATURES = ["prior_return", "range_return", "body_return", "volume_change"]


def train(csv_path: Path, output_path: Path, chunksize: int = 100_000) -> None:
    xtx = np.zeros((len(FEATURES) + 1, len(FEATURES) + 1), dtype=np.float64)
    xty = np.zeros(len(FEATURES) + 1, dtype=np.float64)
    target_sum = 0.0
    target_sum_sq = 0.0
    rows = 0
    previous = None

    for chunk in pd.read_csv(csv_path, usecols=["open", "high", "low", "close", "volume"], chunksize=chunksize):
        if previous is not None:
            chunk = pd.concat([previous, chunk], ignore_index=True)
        for column in chunk.columns:
            chunk[column] = pd.to_numeric(chunk[column], errors="coerce")
        frame = pd.DataFrame({
            "prior_return": chunk["close"].pct_change(),
            "range_return": chunk["high"] / chunk["low"] - 1.0,
            "body_return": chunk["close"] / chunk["open"] - 1.0,
            "volume_change": chunk["volume"].pct_change(),
            "target": chunk["close"].shift(-1) / chunk["close"] - 1.0,
        }).replace([np.inf, -np.inf], np.nan).dropna()
        previous = chunk.tail(1)
        if frame.empty:
            continue
        frame[FEATURES] = frame[FEATURES].clip(-0.1, 0.1)
        frame["target"] = frame["target"].clip(-0.1, 0.1)
        x = np.column_stack([np.ones(len(frame)), frame[FEATURES].to_numpy(dtype=np.float64)])
        y = frame["target"].to_numpy(dtype=np.float64)
        xtx += x.T @ x
        xty += x.T @ y
        target_sum += float(y.sum())
        target_sum_sq += float(np.square(y).sum())
        rows += len(y)

    if rows == 0:
        raise ValueError("No usable OHLCV rows were found in the CSV.")
    regularizer = np.eye(len(FEATURES) + 1) * 1e-6
    regularizer[0, 0] = 0.0
    weights = np.linalg.solve(xtx + regularizer, xty)
    variance = max(target_sum_sq / rows - (target_sum / rows) ** 2, 0.0)
    payload = {
        "model_type": "ridge_linear_next_minute_return",
        "feature_names": FEATURES,
        "intercept": float(weights[0]),
        "coefficients": [float(value) for value in weights[1:]],
        "training_rows": rows,
        "target_stddev": float(np.sqrt(variance)),
        "signal_threshold": float(max(np.sqrt(variance) * 0.15, 0.00005)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Trained on {rows:,} rows and wrote {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=Path("models/spy_return_model.json"))
    args = parser.parse_args()
    train(args.csv, args.output)
