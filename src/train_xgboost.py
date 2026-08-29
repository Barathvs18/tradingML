"""
train_xgboost.py

Trains an XGBoost regressor to predict the NEXT-DAY % RETURN of RELIANCE.NS.

Target: target = (Close_tomorrow - Close_today) / Close_today

Naive baseline: predict 0% return ("no change") — the correct random-walk
baseline for returns. Reconstruct INR price from predicted return for charts.

Two metric tables are reported:
  1. Return metrics  — MAE/RMSE on the predicted % return itself
  2. Price metrics   — MAE/RMSE on the INR price reconstructed from the return
"""

import os
import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt


def report_metrics(label, y_true, y_pred):
    mae  = mean_absolute_error(y_true, y_pred)
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    print(f"  {label:30s}  MAE={mae:.6f}  RMSE={rmse:.6f}")
    return mae, rmse


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_file = os.path.join(base_dir, "data", "reliance_features.csv")
    plot_dir  = os.path.join(base_dir, "results", "plots")
    os.makedirs(plot_dir, exist_ok=True)

    if not os.path.exists(data_file):
        print(f"ERROR: {data_file} not found. Run data_prep.py first.")
        return

    # -- 1. Load data ----------------------------------------------------------
    df = pd.read_csv(data_file, index_col='Date', parse_dates=True)

    # -- 2. Time-based split (no shuffling, no leakage) ------------------------
    # Train: everything up to end of 2025, Test: Jan 2026
    train_mask = df.index <= '2025-12-31'
    test_mask  = (df.index >= '2026-01-01') & (df.index <= '2026-01-31')

    train_df = df.loc[train_mask].copy()
    test_df  = df.loc[test_mask].copy()

    # Features: everything except the target; keep Close for price reconstruction
    features = [c for c in df.columns if c not in ('target', 'Close')]
    X_train, y_train = train_df[features], train_df['target']
    X_test,  y_test  = test_df[features],  test_df['target']
    print(f"Train: {len(X_train)} rows  |  Test: {len(X_test)} rows")

    # -- 3. Naive baseline: always predict 0% return ("no change") -------------
    naive_return_preds  = np.zeros(len(y_test))
    # Reconstruct price: prev_close * (1 + 0) = prev_close
    naive_price_preds   = test_df['Close'].values

    print("\n--- Naive Baseline (predict 0% return each day) ---")
    nb_ret_mae, nb_ret_rmse   = report_metrics("Return", y_test, naive_return_preds)
    # For price, actual next-day price is not directly in test_df; we compute it
    # from the return: actual_next_price = Close * (1 + target)
    actual_next_price = test_df['Close'].values * (1 + y_test.values)
    nb_px_mae, nb_px_rmse     = report_metrics("Price (reconstructed)", actual_next_price, naive_price_preds)

    # -- 4. Train XGBoost on % return target -----------------------------------
    print("\nTraining XGBoost ...")
    model = xgb.XGBRegressor(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42,
        objective='reg:squarederror'
    )
    model.fit(X_train, y_train)

    # -- 5. Predict & evaluate -------------------------------------------------
    xgb_return_preds = model.predict(X_test)
    # Reconstruct INR price from predicted return
    # predicted_price[t] = actual_close[t] * (1 + predicted_return[t])
    xgb_price_preds  = test_df['Close'].values * (1 + xgb_return_preds)

    print("\n--- XGBoost ---")
    xgb_ret_mae, xgb_ret_rmse = report_metrics("Return", y_test, xgb_return_preds)
    xgb_px_mae,  xgb_px_rmse  = report_metrics("Price (reconstructed)", actual_next_price, xgb_price_preds)

    # -- 6. Plot ---------------------------------------------------------------
    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    # Return plot
    axes[0].plot(test_df.index, y_test.values * 100, label='Actual Return (%)', marker='o', color='black')
    axes[0].axhline(0, linestyle='--', color='gray', label='Naive (0%)')
    axes[0].plot(test_df.index, xgb_return_preds * 100, label='XGBoost', marker='x', color='blue')
    axes[0].set_title('XGBoost: Predicted vs Actual Next-Day Return (Jan 2026)')
    axes[0].set_ylabel('Return (%)')
    axes[0].legend(); axes[0].grid(True); axes[0].tick_params(axis='x', rotation=45)

    # Price reconstruction plot
    axes[1].plot(test_df.index, actual_next_price, label='Actual Next-Day Close', marker='o', color='black')
    axes[1].plot(test_df.index, naive_price_preds, label='Naive Baseline', linestyle='--', color='gray')
    axes[1].plot(test_df.index, xgb_price_preds,  label='XGBoost (from return)', marker='x', color='blue')
    axes[1].set_title('XGBoost: Reconstructed Price vs Actual (Jan 2026)')
    axes[1].set_ylabel('Price (INR)')
    axes[1].legend(); axes[1].grid(True); axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "xgboost_predictions.png"))
    print(f"\nPlot saved.")


if __name__ == "__main__":
    main()
