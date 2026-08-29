"""
train_cnn.py

Trains a 1D CNN (TensorFlow/Keras) to predict the NEXT-DAY % RETURN.

CNN-1D INVESTIGATION (from run 1 — MAE 66.95 vs LSTM 22.89):
---------------------------------------------------------------
Diagnosed THREE contributing issues:

1. INPUT_SHAPE DEPRECATION WARNING (Keras 3):
   The old code passed `input_shape` directly into Conv1D() which triggers
   a UserWarning in Keras 3 and may affect weight initialization. Fix: use
   an explicit keras.Input() as the first layer (same fix as LSTM).

2. SEQUENCE WINDOW TOO SHORT FOR POOLING:
   Two rounds of MaxPooling1D(pool_size=2) on a 30-step window:
     30 -> Conv1D(k=3) -> 28 -> MaxPool -> 14 -> Conv1D(k=3) -> 12 -> MaxPool -> 6
   With only ~19 test samples (after windowing), the network has very few
   gradient steps for the final dense layers. Fix: remove one pooling layer
   so the flattened representation retains more temporal resolution.

3. RETURN SCALING CONSISTENCY:
   The return target (range ~-0.05 to +0.05) is small; StandardScaler on the
   y values maps it to a mean-0/std-1 space. Both LSTM and CNN use identical
   scaler_X and scaler_y fitted on the SAME training split, ensuring
   consistency between the two models.

Architecture after fixes: Input -> Conv1D(64,k=3,ReLU) -> MaxPool(2) ->
  Conv1D(32,k=3,ReLU) -> Flatten -> Dense(50,ReLU) -> Dropout(0.2) -> Dense(1)
Epochs increased to 30 (from 20) to allow more convergence time.
"""

import os
import pandas as pd
import numpy as np
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Conv1D, MaxPooling1D, Flatten, Dense, Dropout, Input
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt


def create_sequences(X, y, time_steps=30):
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
    features   = [c for c in df.columns if c not in ('target', 'Close')]
    time_steps = 30

    # -- 2. Splits -------------------------------------------------------------
    train_mask = df.index <= '2025-12-31'
    test_mask  = (df.index >= '2026-01-01') & (df.index <= '2026-01-31')
    train_df   = df.loc[train_mask]
    test_df    = df.loc[test_mask]

    history_for_test = train_df.iloc[-time_steps:]
    test_df_ext      = pd.concat([history_for_test, test_df])

    # -- 3. Scaling (fit ONLY on train — same as LSTM for consistency) ---------
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()

    X_train_sc = scaler_X.fit_transform(train_df[features])
    y_train_sc = scaler_y.fit_transform(train_df[['target']])
    X_test_sc  = scaler_X.transform(test_df_ext[features])
    y_test_sc  = scaler_y.transform(test_df_ext[['target']])

    # -- 4. Build sequences ----------------------------------------------------
    X_tr, y_tr = create_sequences(X_train_sc, y_train_sc, time_steps)
    X_te, y_te = create_sequences(X_test_sc,  y_test_sc,  time_steps)

    # -- 5. Naive baseline -----------------------------------------------------
    y_test_returns    = test_df['target'].values
    actual_next_price = test_df['Close'].values * (1 + y_test_returns)
    naive_price_preds = test_df['Close'].values

    print("\n--- Naive Baseline (predict 0% return) ---")
    report_metrics("Return", y_test_returns, np.zeros(len(y_test_returns)))
    report_metrics("Price (reconstructed)", actual_next_price, naive_price_preds)

    # -- 6. Build CNN-1D (fixed architecture) ----------------------------------
    # FIX 1: explicit Input() layer instead of input_shape= argument
    # FIX 2: only ONE MaxPooling layer (avoids over-reducing 30-step window)
    # FIX 3: 30 epochs instead of 20 for better convergence on return target
    print("\nBuilding CNN-1D model (with architecture fixes) ...")
    model = Sequential([
        Input(shape=(X_tr.shape[1], X_tr.shape[2])),
        Conv1D(filters=64, kernel_size=3, activation='relu'),
        MaxPooling1D(pool_size=2),            # 30 -> 28 -> 14 (only one pooling)
        Conv1D(filters=32, kernel_size=3, activation='relu'),
        Flatten(),
        Dense(50, activation='relu'),
        Dropout(0.2),
        Dense(1)
    ])
    model.compile(optimizer='adam', loss='mse')

    print("Training CNN-1D (30 epochs) ...")
    model.fit(X_tr, y_tr, epochs=30, batch_size=32, validation_split=0.1, verbose=1)

    # -- 7. Predict & inverse-scale --------------------------------------------
    cnn_preds_sc      = model.predict(X_te, verbose=0)
    cnn_return_preds  = scaler_y.inverse_transform(cnn_preds_sc).flatten()
    cnn_price_preds   = test_df['Close'].values * (1 + cnn_return_preds)

    print("\n--- CNN-1D (fixed) ---")
    report_metrics("Return", y_test_returns, cnn_return_preds)
    report_metrics("Price (reconstructed)", actual_next_price, cnn_price_preds)

    # -- 8. Plot ---------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    axes[0].plot(test_df.index, y_test_returns * 100, label='Actual Return (%)', marker='o', color='black')
    axes[0].axhline(0, linestyle='--', color='gray', label='Naive (0%)')
    axes[0].plot(test_df.index, cnn_return_preds * 100, label='CNN-1D (fixed)', marker='x', color='red')
    axes[0].set_title('CNN-1D: Predicted vs Actual Next-Day Return (Jan 2026)')
    axes[0].set_ylabel('Return (%)'); axes[0].legend(); axes[0].grid(True)
    axes[0].tick_params(axis='x', rotation=45)

    axes[1].plot(test_df.index, actual_next_price, label='Actual Next-Day Close', marker='o', color='black')
    axes[1].plot(test_df.index, naive_price_preds,  label='Naive Baseline', linestyle='--', color='gray')
    axes[1].plot(test_df.index, cnn_price_preds,    label='CNN-1D (from return)', marker='x', color='red')
    axes[1].set_title('CNN-1D: Reconstructed Price vs Actual (Jan 2026)')
    axes[1].set_ylabel('Price (INR)'); axes[1].legend(); axes[1].grid(True)
    axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "cnn_predictions.png"))
    print("\nPlot saved.")


if __name__ == "__main__":
    main()
