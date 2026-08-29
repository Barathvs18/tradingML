"""
stacking.py

Final stacking ensemble meta-model.

Data splits (strict, no leakage):
  Train base models : 2020 - Jun 2025
  Train meta-learner: Jul - Dec 2025  (out-of-fold / validation predictions)
  Evaluate          : Jan 2026 only   (never used in any training/tuning step)

Target throughout: next-day % RETURN.
INR price reconstruction (actual_close * (1 + predicted_return)) happens ONLY
at the very end, for reporting and plotting — never fed back into any model.

Two metric tables:
  1. Return metrics  — MAE/RMSE on predicted return
  2. Price metrics   — MAE/RMSE on reconstructed INR price
"""

import os
import pandas as pd
import numpy as np
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Conv1D, MaxPooling1D, Flatten, Dense, Dropout, Input
import matplotlib.pyplot as plt


# --------------------------------------------------------------------------- #
def create_sequences(X, y, time_steps=30):
    Xs, ys = [], []
    for i in range(len(X) - time_steps):
        Xs.append(X[i:(i + time_steps)])
        ys.append(y[i + time_steps])
    return np.array(Xs), np.array(ys)


def report_metrics(label, y_true, y_pred):
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mape = np.mean(np.abs((y_true - y_pred) / (np.abs(y_true) + 1e-8))) * 100
    return mae, rmse, mape


# --------------------------------------------------------------------------- #
def main():
    base_dir    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_file   = os.path.join(base_dir, "data", "reliance_features.csv")
    results_dir = os.path.join(base_dir, "results")
    plot_dir    = os.path.join(results_dir, "plots")
    os.makedirs(results_dir, exist_ok=True)
    os.makedirs(plot_dir,    exist_ok=True)

    if not os.path.exists(data_file):
        print(f"ERROR: {data_file} not found. Run data_prep.py first.")
        return

    # ── 1. Load data ─────────────────────────────────────────────────────────
    print("Loading data ...")
    df = pd.read_csv(data_file, index_col='Date', parse_dates=True)
    features   = [c for c in df.columns if c not in ('target', 'Close')]
    time_steps = 30

    # ── 2. Splits ─────────────────────────────────────────────────────────────
    # Base models train on 2020 - Jun 2025
    # Meta-learner trains on Jul - Dec 2025 (validation)
    # Jan 2026 = held-out test, never used until final evaluation
    train_mask = df.index <= '2025-06-30'
    val_mask   = (df.index >= '2025-07-01') & (df.index <= '2025-12-31')
    test_mask  = (df.index >= '2026-01-01') & (df.index <= '2026-01-31')

    train_df = df.loc[train_mask]
    val_df   = df.loc[val_mask]
    test_df  = df.loc[test_mask]

    X_train, y_train = train_df[features], train_df['target']
    X_val,   y_val   = val_df[features],   val_df['target']
    X_test,  y_test  = test_df[features],  test_df['target']

    # For price reconstruction (done only at the end)
    actual_next_price_val  = val_df['Close'].values  * (1 + y_val.values)
    actual_next_price_test = test_df['Close'].values * (1 + y_test.values)
    naive_price_test       = test_df['Close'].values

    # ── 3. Train tree base models ─────────────────────────────────────────────
    print("Training XGBoost ...")
    xgb_m = xgb.XGBRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42)
    xgb_m.fit(X_train, y_train)

    print("Training LightGBM ...")
    lgb_m = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42, verbose=-1)
    lgb_m.fit(X_train, y_train)

    print("Training Random Forest ...")
    rf_m = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42, n_jobs=-1)
    rf_m.fit(X_train, y_train)

    # Predict returns on val and test
    xgb_val, xgb_test = xgb_m.predict(X_val), xgb_m.predict(X_test)
    lgb_val, lgb_test = lgb_m.predict(X_val), lgb_m.predict(X_test)
    rf_val,  rf_test  = rf_m.predict(X_val),  rf_m.predict(X_test)

    # ── 4. Scale & sequence data for DL models ─────────────────────────────────
    print("Preparing sequence data for DL models ...")
    scaler_X = StandardScaler()
    scaler_y = StandardScaler()
    scaler_X.fit(train_df[features])
    scaler_y.fit(train_df[['target']])

    # We need 30 days of history before the first val and test rows for sequencing
    hist_for_val  = train_df.iloc[-time_steps:]
    val_ext       = pd.concat([hist_for_val, val_df])

    hist_for_test = val_df.iloc[-time_steps:]
    test_ext      = pd.concat([hist_for_test, test_df])

    def scale_and_seq(df_ext):
        Xsc = scaler_X.transform(df_ext[features])
        ysc = scaler_y.transform(df_ext[['target']])
        return create_sequences(Xsc, ysc, time_steps)

    X_tr_dl, y_tr_dl = create_sequences(
        scaler_X.transform(train_df[features]),
        scaler_y.transform(train_df[['target']]),
        time_steps
    )
    X_val_dl, y_val_dl   = scale_and_seq(val_ext)
    X_test_dl, y_test_dl = scale_and_seq(test_ext)

    # ── 5. LSTM ───────────────────────────────────────────────────────────────
    print("Training LSTM ...")
    lstm = Sequential([
        Input(shape=(X_tr_dl.shape[1], X_tr_dl.shape[2])),
        LSTM(50, return_sequences=True),
        Dropout(0.2),
        LSTM(50),
        Dropout(0.2),
        Dense(1)
    ])
    lstm.compile(optimizer='adam', loss='mse')
    lstm.fit(X_tr_dl, y_tr_dl, epochs=20, batch_size=32, verbose=0)

    lstm_val  = scaler_y.inverse_transform(lstm.predict(X_val_dl,  verbose=0)).flatten()
    lstm_test = scaler_y.inverse_transform(lstm.predict(X_test_dl, verbose=0)).flatten()

    # ── 6. CNN-1D (with architecture fixes) ───────────────────────────────────
    print("Training CNN-1D (fixed architecture) ...")
    cnn = Sequential([
        Input(shape=(X_tr_dl.shape[1], X_tr_dl.shape[2])),
        Conv1D(64, kernel_size=3, activation='relu'),
        MaxPooling1D(pool_size=2),          # ONE pooling layer only
        Conv1D(32, kernel_size=3, activation='relu'),
        Flatten(),
        Dense(50, activation='relu'),
        Dropout(0.2),
        Dense(1)
    ])
    cnn.compile(optimizer='adam', loss='mse')
    cnn.fit(X_tr_dl, y_tr_dl, epochs=30, batch_size=32, verbose=0)

    cnn_val  = scaler_y.inverse_transform(cnn.predict(X_val_dl,  verbose=0)).flatten()
    cnn_test = scaler_y.inverse_transform(cnn.predict(X_test_dl, verbose=0)).flatten()

    # ── 7. Stack: meta-learner on RETURN predictions, trained on val set ──────
    # The meta-learner NEVER sees Jan 2026; it learns on Jul-Dec 2025.
    print("Training meta-learner (Linear Regression on val-set return predictions) ...")
    val_meta  = np.column_stack([xgb_val,  lgb_val,  rf_val,  lstm_val,  cnn_val])
    test_meta = np.column_stack([xgb_test, lgb_test, rf_test, lstm_test, cnn_test])

    meta = LinearRegression()
    meta.fit(val_meta, y_val)
    print(f"  Meta-learner weights: XGB={meta.coef_[0]:.3f}  LGB={meta.coef_[1]:.3f}  "
          f"RF={meta.coef_[2]:.3f}  LSTM={meta.coef_[3]:.3f}  CNN={meta.coef_[4]:.3f}")

    stack_test_returns = meta.predict(test_meta)
    avg_test_returns   = test_meta.mean(axis=1)

    # ── 8. Convert returns -> prices (ONLY here, for reporting) ───────────────
    def to_price(returns):
        return test_df['Close'].values * (1 + returns)

    prices = {
        'Naive Baseline'  : naive_price_test,
        'XGBoost'         : to_price(xgb_test),
        'LightGBM'        : to_price(lgb_test),
        'Random Forest'   : to_price(rf_test),
        'LSTM'            : to_price(lstm_test),
        'CNN-1D'          : to_price(cnn_test),
        'Average Ensemble': to_price(avg_test_returns),
        'Stacked Ensemble': to_price(stack_test_returns),
    }
    returns = {
        'Naive Baseline'  : np.zeros(len(y_test)),
        'XGBoost'         : xgb_test,
        'LightGBM'        : lgb_test,
        'Random Forest'   : rf_test,
        'LSTM'            : lstm_test,
        'CNN-1D'          : cnn_test,
        'Average Ensemble': avg_test_returns,
        'Stacked Ensemble': stack_test_returns,
    }

    # ── 9. Build metrics table ─────────────────────────────────────────────────
    records = []
    for name in prices:
        ret_mae, ret_rmse, _  = report_metrics(name, y_test.values, returns[name])
        px_mae,  px_rmse,  _  = report_metrics(name, actual_next_price_test, prices[name])
        mape = np.mean(np.abs((actual_next_price_test - prices[name]) / actual_next_price_test)) * 100
        records.append({
            'Model'          : name,
            'Return MAE'     : ret_mae,
            'Return RMSE'    : ret_rmse,
            'Price MAE (INR)': px_mae,
            'Price RMSE (INR)': px_rmse,
            'Price MAPE (%)'  : mape,
        })

    metrics_df = pd.DataFrame(records)
    csv_path = os.path.join(results_dir, "metrics.csv")
    metrics_df.to_csv(csv_path, index=False)

    print("\n" + "="*78)
    print("FINAL RESULTS — Jan 2026 Test Set")
    print("="*78)
    print(metrics_df.to_string(index=False))
    print(f"\nSaved to {csv_path}")

    # ── 10. Final plot ─────────────────────────────────────────────────────────
    fig, axes = plt.subplots(2, 1, figsize=(14, 12))

    # Return panel
    axes[0].plot(test_df.index, y_test.values * 100, 'ko-', label='Actual Return (%)', linewidth=2)
    axes[0].axhline(0, linestyle='--', color='gray', label='Naive (0%)')
    axes[0].plot(test_df.index, stack_test_returns * 100, 'rs-', label='Stacked Ensemble', linewidth=2)
    axes[0].plot(test_df.index, avg_test_returns * 100,   'b^:', label='Average Ensemble')
    axes[0].set_title('Final Stacking: Predicted vs Actual Next-Day Return (Jan 2026)')
    axes[0].set_ylabel('Return (%)'); axes[0].legend(); axes[0].grid(True)
    axes[0].tick_params(axis='x', rotation=45)

    # Price panel
    axes[1].plot(test_df.index, actual_next_price_test, 'ko-', label='Actual Next-Day Close', linewidth=2)
    axes[1].plot(test_df.index, naive_price_test,         '--', color='gray', label='Naive Baseline')
    axes[1].plot(test_df.index, prices['Stacked Ensemble'], 'rs-', label='Stacked Ensemble', linewidth=2)
    axes[1].plot(test_df.index, prices['LightGBM'],         'g^:', label='LightGBM')
    axes[1].plot(test_df.index, prices['Random Forest'],    'b^:', label='Random Forest')
    axes[1].set_title('Final Stacking: Reconstructed Price vs Actual (Jan 2026)')
    axes[1].set_ylabel('Price (INR)'); axes[1].legend(); axes[1].grid(True)
    axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    final_plot = os.path.join(plot_dir, "final_stacking.png")
    plt.savefig(final_plot)
    print(f"Plot saved to {final_plot}")


if __name__ == "__main__":
    main()
