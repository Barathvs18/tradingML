"""
get_stacked_predictions.py

Runs the full 5-model stacking ensemble and outputs a clean predictions table
for Jan 2026 to results/jan2026_stacked_predictions.csv.

No leakage: meta-learner is trained ONLY on val-set (Jul-Dec 2025) predictions,
            Jan 2026 is used for final evaluation only.

Run from src/ directory:
    cd src
    python get_stacked_predictions.py

Base model params: tuned Optuna-NSGA-II params from genetic_tuning.py.
"""

import os
import sys
import numpy as np
import pandas as pd
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import (LSTM, Conv1D, MaxPooling1D,
                                     Flatten, Dense, Dropout, Input)

# -- Paths --------------------------------------------------------------------
SRC_DIR     = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SRC_DIR)
DATA_FILE   = os.path.join(PROJECT_DIR, "data", "reliance_features.csv")
RESULTS_DIR = os.path.join(PROJECT_DIR, "results")
OUT_FILE    = os.path.join(RESULTS_DIR, "jan2026_stacked_predictions.csv")
os.makedirs(RESULTS_DIR, exist_ok=True)

# -- Best tuned hyperparameters from genetic_tuning.py -----------------------
BEST_XGB = dict(n_estimators=89, learning_rate=0.055238, max_depth=3,
                subsample=0.9465, random_state=42, objective='reg:squarederror')
BEST_LGB = dict(n_estimators=107, learning_rate=0.03232, max_depth=5,
                num_leaves=33, random_state=42, verbose=-1)
BEST_RF  = dict(n_estimators=121, max_depth=3, min_samples_split=7,
                random_state=42, n_jobs=-1)

TIME_STEPS = 30   # sequence window for LSTM / CNN

# ---------------------------------------------------------------------------
def create_sequences(X, y, time_steps=30):
    Xs, ys = [], []
    for i in range(len(X) - time_steps):
        Xs.append(X[i:(i + time_steps)])
        ys.append(y[i + time_steps])
    return np.array(Xs), np.array(ys)


def build_lstm(input_shape):
    m = Sequential([
        Input(shape=input_shape),
        LSTM(50, return_sequences=True),
        Dropout(0.2),
        LSTM(50),
        Dropout(0.2),
        Dense(1)
    ])
    m.compile(optimizer='adam', loss='mse')
    return m


def build_cnn(input_shape):
    m = Sequential([
        Input(shape=input_shape),
        Conv1D(64, kernel_size=3, activation='relu'),
        MaxPooling1D(pool_size=2),
        Conv1D(32, kernel_size=3, activation='relu'),
        Flatten(),
        Dense(50, activation='relu'),
        Dropout(0.2),
        Dense(1)
    ])
    m.compile(optimizer='adam', loss='mse')
    return m


# ---------------------------------------------------------------------------
def main():
    # -- 1. Load data ---------------------------------------------------------
    print(f"Loading {DATA_FILE} ...")
    df = pd.read_csv(DATA_FILE, index_col=0, parse_dates=True)

    # 'target' column is already the next-day % return (set by data_prep.py)
    features = [c for c in df.columns if c not in ("target", "Close")]

    # -- 2. Splits (STRICT — no leakage) -------------------------------------
    # Base models trained on 2020-Mar to 2025-Jun
    # Meta-learner trained on val predictions (2025-Jul to 2025-Dec)
    # Jan 2026 = final evaluation only
    train_mask = df.index <= "2025-06-30"
    val_mask   = (df.index >= "2025-07-01") & (df.index <= "2025-12-31")
    test_mask  = (df.index >= "2026-01-01") & (df.index < "2026-02-01")

    train_df = df.loc[train_mask]
    val_df   = df.loc[val_mask]
    test_df  = df.loc[test_mask]

    X_train, y_train = train_df[features], train_df["target"]
    X_val,   y_val   = val_df[features],   val_df["target"]
    X_test,  y_test  = test_df[features],  test_df["target"]

    print(f"Train: {len(X_train)}  Val: {len(X_val)}  Test: {len(X_test)}")

    # -- 3. Train tree base models -------------------------------------------
    print("\nTraining XGBoost (tuned) ...")
    xgb_m = xgb.XGBRegressor(**BEST_XGB)
    xgb_m.fit(X_train, y_train)

    print("Training LightGBM (tuned) ...")
    lgb_m = lgb.LGBMRegressor(**BEST_LGB)
    lgb_m.fit(X_train, y_train)

    print("Training Random Forest (tuned) ...")
    rf_m  = RandomForestRegressor(**BEST_RF)
    rf_m.fit(X_train, y_train)

    # Val + Test predictions from tree models
    xgb_val,  xgb_test  = xgb_m.predict(X_val),  xgb_m.predict(X_test)
    lgb_val,  lgb_test  = lgb_m.predict(X_val),  lgb_m.predict(X_test)
    rf_val,   rf_test   = rf_m.predict(X_val),   rf_m.predict(X_test)

    # -- 4. Scale + sequence data for DL models ------------------------------
    print("Scaling and sequencing data for DL models ...")
    scaler_X = StandardScaler().fit(train_df[features])
    scaler_y = StandardScaler().fit(train_df[["target"]])

    X_tr_sc = scaler_X.transform(train_df[features])
    y_tr_sc = scaler_y.transform(train_df[["target"]])

    # Need 30-day history before val and test for sequencing
    hist_val  = train_df.iloc[-TIME_STEPS:]
    val_ext   = pd.concat([hist_val, val_df])

    hist_test = val_df.iloc[-TIME_STEPS:]
    test_ext  = pd.concat([hist_test, test_df])

    def seq(df_ext):
        Xs = scaler_X.transform(df_ext[features])
        ys = scaler_y.transform(df_ext[["target"]])
        return create_sequences(Xs, ys, TIME_STEPS)

    X_tr_dl, y_tr_dl   = create_sequences(X_tr_sc, y_tr_sc, TIME_STEPS)
    X_val_dl, _         = seq(val_ext)
    X_test_dl, _        = seq(test_ext)

    # -- 5. Train LSTM --------------------------------------------------------
    print("Training LSTM (20 epochs) ...")
    lstm_m = build_lstm((X_tr_dl.shape[1], X_tr_dl.shape[2]))
    lstm_m.fit(X_tr_dl, y_tr_dl, epochs=20, batch_size=32,
               validation_split=0.1, verbose=0)

    lstm_val  = scaler_y.inverse_transform(
                    lstm_m.predict(X_val_dl,  verbose=0)).flatten()
    lstm_test = scaler_y.inverse_transform(
                    lstm_m.predict(X_test_dl, verbose=0)).flatten()

    # -- 6. Train CNN-1D (fixed architecture: 1 pooling, 30 epochs) ----------
    print("Training CNN-1D (30 epochs) ...")
    cnn_m = build_cnn((X_tr_dl.shape[1], X_tr_dl.shape[2]))
    cnn_m.fit(X_tr_dl, y_tr_dl, epochs=30, batch_size=32,
              validation_split=0.1, verbose=0)

    cnn_val  = scaler_y.inverse_transform(
                   cnn_m.predict(X_val_dl,  verbose=0)).flatten()
    cnn_test = scaler_y.inverse_transform(
                   cnn_m.predict(X_test_dl, verbose=0)).flatten()

    # -- 7. Train meta-learner on VAL predictions (no leakage) ---------------
    print("Training Linear Regression meta-learner on val-set predictions ...")
    val_meta  = np.column_stack([xgb_val,  lgb_val,  rf_val,  lstm_val,  cnn_val])
    test_meta = np.column_stack([xgb_test, lgb_test, rf_test, lstm_test, cnn_test])

    meta = LinearRegression()
    meta.fit(val_meta, y_val)

    print(f"  Weights: XGB={meta.coef_[0]:.3f}  LGB={meta.coef_[1]:.3f}  "
          f"RF={meta.coef_[2]:.3f}  LSTM={meta.coef_[3]:.3f}  "
          f"CNN={meta.coef_[4]:.3f}  bias={meta.intercept_:.4f}")

    # -- 8. Stacked return prediction -> price --------------------------------
    stacked_returns = meta.predict(test_meta)
    predicted_close = test_df["Close"].values * (1 + stacked_returns)
    actual_close    = test_df["Close"].values * (1 + y_test.values)

    # -- 9. Build output table ------------------------------------------------
    result = pd.DataFrame({
        "Date"            : test_df.index.strftime("%Y-%m-%d"),
        "Actual_Close"    : np.round(actual_close,    2),
        "Predicted_Close" : np.round(predicted_close, 2),
        "Error_INR"       : np.round(np.abs(actual_close - predicted_close), 2),
        "Error_Pct"       : np.round(
            np.abs(actual_close - predicted_close) / actual_close * 100, 3),
    })

    mae  = result["Error_INR"].mean()
    mape = result["Error_Pct"].mean()

    print(f"\n{'='*60}")
    print(f"  Stacked Ensemble Predictions — Jan 2026")
    print(f"{'='*60}")
    print(result.to_string(index=False))
    print(f"{'='*60}")
    print(f"  MAE : {mae:.2f} INR")
    print(f"  MAPE: {mape:.3f}%")
    print(f"{'='*60}")

    result.to_csv(OUT_FILE, index=False)
    print(f"\nSaved to {OUT_FILE}")


if __name__ == "__main__":
    main()
