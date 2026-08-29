"""
get_predictions.py

Runs the best single model (Random Forest with tuned params) on the Jan 2026
test set and saves a clean date/actual/predicted table to results/.

Run from src/ directory:
    cd src
    python get_predictions.py
"""

import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor

# -- Paths (relative to this file, works from any working directory) ----------
SRC_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DATA_FILE   = os.path.join(PROJECT_DIR, "data", "reliance_features.csv")
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
OUT_FILE    = os.path.join(RESULTS_DIR, "jan2026_predictions.csv")

os.makedirs(RESULTS_DIR, exist_ok=True)

# -- Load features CSV --------------------------------------------------------
print(f"Loading {DATA_FILE} ...")
data = pd.read_csv(DATA_FILE, index_col=0, parse_dates=True)

# target column already holds next-day % return (set by data_prep.py)
# Features: everything except the target column and Close (kept for price recon)
features = [c for c in data.columns if c not in ("target", "Close")]

# -- Strict time-based split (no shuffling, no leakage) -----------------------
train = data[data.index <  "2026-01-01"]
test  = data[(data.index >= "2026-01-01") & (data.index < "2026-02-01")]

X_train, y_train = train[features], train["target"]
X_test           = test[features]

print(f"Train: {len(X_train)} rows  |  Test: {len(X_test)} rows")

# -- Train Random Forest with the best Optuna-tuned params -------------------
print("Training Random Forest (tuned params) ...")
model = RandomForestRegressor(
    n_estimators=121,
    max_depth=3,
    min_samples_split=7,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)

# -- Predict next-day % return, reconstruct INR price ------------------------
predicted_returns = model.predict(X_test)
predicted_prices  = test["Close"].values * (1 + predicted_returns)

# Actual next-day close = today's close * (1 + actual return)
actual_prices = test["Close"].values * (1 + test["target"].values)

# -- Build clean output table ------------------------------------------------
result = pd.DataFrame({
    "Date"            : test.index.strftime("%Y-%m-%d"),
    "Actual_Close"    : np.round(actual_prices, 2),
    "Predicted_Close" : np.round(predicted_prices, 2),
    "Error_INR"       : np.round(np.abs(actual_prices - predicted_prices), 2),
    "Error_Pct"       : np.round(
        np.abs(actual_prices - predicted_prices) / actual_prices * 100, 3
    ),
})

mae  = result["Error_INR"].mean()
mape = result["Error_Pct"].mean()

print(f"\n{'='*55}")
print(f"  Random Forest Predictions — Jan 2026")
print(f"{'='*55}")
print(result.to_string(index=False))
print(f"{'='*55}")
print(f"  MAE : {mae:.2f} INR")
print(f"  MAPE: {mape:.3f}%")
print(f"{'='*55}")

result.to_csv(OUT_FILE, index=False)
print(f"\nSaved to {OUT_FILE}")