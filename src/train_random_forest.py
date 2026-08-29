"""
train_random_forest.py

Trains a Random Forest regressor to predict the NEXT-DAY % RETURN of RELIANCE.NS.
Same dual-metric reporting as the other tree scripts.
Naive baseline = predict 0% return (random-walk baseline).
"""

import os
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
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

    df = pd.read_csv(data_file, index_col='Date', parse_dates=True)

    train_mask = df.index <= '2025-12-31'
    test_mask  = (df.index >= '2026-01-01') & (df.index <= '2026-01-31')
    train_df   = df.loc[train_mask].copy()
    test_df    = df.loc[test_mask].copy()

    features = [c for c in df.columns if c not in ('target', 'Close')]
    X_train, y_train = train_df[features], train_df['target']
    X_test,  y_test  = test_df[features],  test_df['target']

    actual_next_price = test_df['Close'].values * (1 + y_test.values)
    naive_return_preds = np.zeros(len(y_test))
    naive_price_preds  = test_df['Close'].values

    print(f"Train: {len(X_train)} rows  |  Test: {len(X_test)} rows")
    print("\n--- Naive Baseline (predict 0% return) ---")
    report_metrics("Return", y_test, naive_return_preds)
    report_metrics("Price (reconstructed)", actual_next_price, naive_price_preds)

    print("\nTraining Random Forest ...")
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=5,
        random_state=42,
        n_jobs=-1
    )
    model.fit(X_train, y_train)

    rf_return_preds = model.predict(X_test)
    rf_price_preds  = test_df['Close'].values * (1 + rf_return_preds)

    print("\n--- Random Forest ---")
    report_metrics("Return", y_test, rf_return_preds)
    report_metrics("Price (reconstructed)", actual_next_price, rf_price_preds)

    fig, axes = plt.subplots(2, 1, figsize=(12, 10))

    axes[0].plot(test_df.index, y_test.values * 100, label='Actual Return (%)', marker='o', color='black')
    axes[0].axhline(0, linestyle='--', color='gray', label='Naive (0%)')
    axes[0].plot(test_df.index, rf_return_preds * 100, label='Random Forest', marker='x', color='orange')
    axes[0].set_title('Random Forest: Predicted vs Actual Next-Day Return (Jan 2026)')
    axes[0].set_ylabel('Return (%)'); axes[0].legend(); axes[0].grid(True)
    axes[0].tick_params(axis='x', rotation=45)

    axes[1].plot(test_df.index, actual_next_price, label='Actual Next-Day Close', marker='o', color='black')
    axes[1].plot(test_df.index, naive_price_preds, label='Naive Baseline', linestyle='--', color='gray')
    axes[1].plot(test_df.index, rf_price_preds,   label='RF (from return)', marker='x', color='orange')
    axes[1].set_title('Random Forest: Reconstructed Price vs Actual (Jan 2026)')
    axes[1].set_ylabel('Price (INR)'); axes[1].legend(); axes[1].grid(True)
    axes[1].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(os.path.join(plot_dir, "rf_predictions.png"))
    print("\nPlot saved.")


if __name__ == "__main__":
    main()
