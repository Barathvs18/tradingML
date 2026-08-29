"""
train_lstm.py

Trains an LSTM model (TensorFlow/Keras) to predict the NEXT-DAY % RETURN.

Key design choices:
- Input: sequences of the past 30 days of features (StandardScaler on train only)
- Target scaler: fits on return values (small, ~-0.05 to +0.05)
- Naive baseline: 0% return every day
- After prediction: reconstruct INR price = actual_close_today * (1 + pred_return)
- Two separate metric tables: return metrics + price metrics
"""

import os
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt


def create_sequences(X, y, time_steps=30):
    """Build (X_seq, y_seq) arrays: each X window has time_steps rows of features,
    y is the single target value at position time_steps ahead."""
    Xs, ys = [], []
    for i in range(len(X) - time_steps):
        Xs.append(X[i:(i + time_steps)])
        ys.append(y[i + time_steps])
    return np.array(Xs), np.array(ys)


def report_metrics(label, y_true, y_pred):
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    print(f"  {label:30s}  MAE={mae:.6f}  RMSE={rmse:.6f}")
    return mae, rmse


def main():
    base_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_file = os.path.join(base_dir, "data", "reliance_features.csv")
    plot_dir  = os.path.join(base_dir, "results", "plots")
    os.makedirs(plot_dir, exist_ok=True)

    if not os.path.exists(data_file):
        print(f"ERROR: {data_file} not found. Run data_prep.py first.")
        return

    # -- 1. Load data ----------------------------------------------------------
    df = pd.read_csv(data_file, index_col='Date', parse_dates=True)
    features = [c for c in df.columns if c not in ('target', 'Close')]
    time_steps = 30

    # -- 2. Splits -------------------------------------------------------------
    train_mask = df.index <= '2025-12-31'
    test_mask  = (df.index >= '2026-01-01') & (df.index <= '2026-01-31')
    train_df   = df.loc[train_mask]
    test_df    = df.loc[test_mask]

    # For test sequences we need the 30 days immediately before the first test date
    history_for_test = train_df.iloc[-time_steps:]
    test_df_ext      = pd.concat([history_for_test, test_df])

    # -- 3. Scaling (fit ONLY on train data to prevent leakage) ----------------
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()

    X_train_sc = scaler_X.fit_transform(train_df[features])
    # Return target is already small; scaling helps LSTM gradient stability
    y_train_sc = scaler_y.fit_transform(train_df[['target']])

    X_test_sc  = scaler_X.transform(test_df_ext[features])
    y_test_sc  = scaler_y.transform(test_df_ext[['target']])

    # -- 4. Build sequences ----------------------------------------------------
    X_tr, y_tr = create_sequences(X_train_sc, y_train_sc, time_steps)
    X_te, y_te = create_sequences(X_test_sc,  y_test_sc,  time_steps)

    # -- 5. Naive baseline on actual returns -----------------------------------
    y_test_returns = test_df['target'].values
    actual_next_price = test_df['Close'].values * (1 + y_test_returns)
    naive_price_preds  = test_df['Close'].values

    print("\n--- Naive Baseline (predict 0% return) ---")
    report_metrics("Return", y_test_returns, np.zeros(len(y_test_returns)))
    report_metrics("Price (reconstructed)", actual_next_price, naive_price_preds)

    # -- 6. Build and train LSTM -----------------------------------------------
    print("\nBuilding LSTM model ...")
    model = Sequential([
        Input(shape=(X_tr.shape[1], X_tr.shape[2])),
        LSTM(50, return_sequences=True),
        Dropout(0.2),
        LSTM(50),
        Dropout(0.2),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')

    print("Training LSTM (20 epochs) ...")
    model.fit(X_tr, y_tr, epochs=20, batch_size=32, validation_split=0.1, verbose=1)

    # -- 7. Predict & inverse-scale --------------------------------------------
    lstm_preds_sc = model.predict(X_te, verbose=0)
    lstm_return_preds = scaler_y.inverse_transform(lstm_preds_sc).flatten()
    lstm_price_preds  = test_df['Close'].values * (1 + lstm_return_preds)

    print("\n--- LSTM ---")
    report_metrics("Return", y_test_returns, lstm_return_preds)
    report_metrics("Price (reconstructed)", actual_next_price, lstm_price_preds)

    # -- 8. Plot ---------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    axes[0].plot(test_df.index, y_test_returns * 100, label='Actual Return (%)', marker='o', color='black')
    axes[0].axhline(0, linestyle='--', color='gray', label='Naive (0%)')
    axes[0].plot(test_df.index, lstm_return_preds * 100, label='LSTM', marker='x', color='purple')
    axes[0].set_title('LSTM: Predicted vs Actual Next-Day Return (Jan 2026)')
    axes[0].set_ylabel('Return (%)'); axes[0].legend(); axes[0].grid(True)
    axes[0].tick_params(axis='x', rotation=45)

    axes[1].plot(test_df.index, actual_next_price, label='Actual Next-Day Close', marker='o', color='black')
    axes[1].plot(test_df.index, naive_price_preds,  label='Naive Baseline', linestyle='--', color='gray')
    axes[1].plot(test_df.index, lstm_price_preds,   label='LSTM (from return)', marker='x', color='purple')
    axes[1].set_title('LSTM: Reconstructed Price vs Actual (Jan 2026)')
    axes[1].set_ylabel('Price (INR)'); axes[1].legend(); axes[1].grid(True)
    axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "lstm_predictions.png"))
    print("\nPlot saved.")


if __name__ == "__main__":
    main()
