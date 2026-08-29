"""
genetic_tuning.py

Uses Optuna with an NSGA-II sampler (genetic/evolutionary search) to tune
hyperparameters for XGBoost, LightGBM, and Random Forest.

Target: next-day % RETURN (updated from raw price — see README).
Validation split: last 6 months of 2025 (Jul-Dec), strictly within training
  data — Jan 2026 is never touched during tuning.
Objective: minimize MAE on the RETURN predictions on the validation split.
"""

import os
import pandas as pd
import numpy as np
import optuna
import xgboost as xgb
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# Suppress verbose Optuna trial logs
optuna.logging.set_verbosity(optuna.logging.WARNING)


def main():
    base_dir  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_file = os.path.join(base_dir, "data", "reliance_features.csv")
    results_dir = os.path.join(base_dir, "results")
    os.makedirs(results_dir, exist_ok=True)

    if not os.path.exists(data_file):
        print(f"ERROR: {data_file} not found.")
        return

    # -- 1. Load and split data ------------------------------------------------
    df = pd.read_csv(data_file, index_col='Date', parse_dates=True)
    features = [c for c in df.columns if c not in ('target', 'Close')]

    # Full training period (used to retrain final models after tuning)
    full_train_mask = df.index <= '2025-12-31'
    # For tuning: train up to Jun 2025, validate Jul-Dec 2025
    tune_train_mask = df.index <= '2025-06-30'
    tune_val_mask   = (df.index >= '2025-07-01') & (df.index <= '2025-12-31')
    test_mask       = (df.index >= '2026-01-01') & (df.index <= '2026-01-31')

    X_full_train = df.loc[full_train_mask, features]
    y_full_train = df.loc[full_train_mask, 'target']

    X_tune_tr = df.loc[tune_train_mask, features]
    y_tune_tr = df.loc[tune_train_mask, 'target']
    X_val     = df.loc[tune_val_mask, features]
    y_val     = df.loc[tune_val_mask, 'target']

    X_test    = df.loc[test_mask, features]
    y_test    = df.loc[test_mask, 'target']
    close_test = df.loc[test_mask, 'Close'].values

    print(f"Tune-train: {len(X_tune_tr)}  Val: {len(X_val)}  Test: {len(X_test)}")

    sampler = optuna.samplers.NSGAIISampler(seed=42)

    # -- 2. Tune XGBoost -------------------------------------------------------
    def obj_xgb(trial):
        p = dict(
            n_estimators  = trial.suggest_int('n_estimators', 50, 300),
            learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3),
            max_depth     = trial.suggest_int('max_depth', 3, 10),
            subsample     = trial.suggest_float('subsample', 0.6, 1.0),
            random_state  = 42,
            objective     = 'reg:squarederror',
        )
        m = xgb.XGBRegressor(**p)
        m.fit(X_tune_tr, y_tune_tr)
        return mean_absolute_error(y_val, m.predict(X_val))

    print("Tuning XGBoost (15 trials) ...")
    study_xgb = optuna.create_study(direction='minimize', sampler=sampler)
    study_xgb.optimize(obj_xgb, n_trials=15)
    best_xgb = study_xgb.best_params
    print(f"  Best XGB params: {best_xgb}  (val MAE {study_xgb.best_value:.6f})")

    # -- 3. Tune LightGBM ------------------------------------------------------
    def obj_lgb(trial):
        p = dict(
            n_estimators  = trial.suggest_int('n_estimators', 50, 300),
            learning_rate = trial.suggest_float('learning_rate', 0.01, 0.3),
            max_depth     = trial.suggest_int('max_depth', 3, 10),
            num_leaves    = trial.suggest_int('num_leaves', 20, 100),
            random_state  = 42,
            verbose       = -1,
        )
        m = lgb.LGBMRegressor(**p)
        m.fit(X_tune_tr, y_tune_tr)
        return mean_absolute_error(y_val, m.predict(X_val))

    print("Tuning LightGBM (15 trials) ...")
    study_lgb = optuna.create_study(direction='minimize', sampler=sampler)
    study_lgb.optimize(obj_lgb, n_trials=15)
    best_lgb = study_lgb.best_params
    print(f"  Best LGB params: {best_lgb}  (val MAE {study_lgb.best_value:.6f})")

    # -- 4. Tune Random Forest -------------------------------------------------
    def obj_rf(trial):
        p = dict(
            n_estimators     = trial.suggest_int('n_estimators', 50, 300),
            max_depth        = trial.suggest_int('max_depth', 3, 15),
            min_samples_split = trial.suggest_int('min_samples_split', 2, 10),
            random_state     = 42,
            n_jobs           = -1,
        )
        m = RandomForestRegressor(**p)
        m.fit(X_tune_tr, y_tune_tr)
        return mean_absolute_error(y_val, m.predict(X_val))

    print("Tuning Random Forest (10 trials) ...")
    study_rf = optuna.create_study(direction='minimize', sampler=sampler)
    study_rf.optimize(obj_rf, n_trials=10)
    best_rf = study_rf.best_params
    print(f"  Best RF params:  {best_rf}  (val MAE {study_rf.best_value:.6f})")

    # -- 5. Retrain best models on full 2020-2025 data, evaluate on Jan 2026 ---
    print("\nRetraining on full 2020-2025 data and evaluating on Jan 2026 ...")

    best_xgb.update({'random_state': 42, 'objective': 'reg:squarederror'})
    final_xgb = xgb.XGBRegressor(**best_xgb)
    final_xgb.fit(X_full_train, y_full_train)
    xgb_test_returns = final_xgb.predict(X_test)
    xgb_ret_mae = mean_absolute_error(y_test, xgb_test_returns)

    best_lgb.update({'random_state': 42, 'verbose': -1})
    final_lgb = lgb.LGBMRegressor(**best_lgb)
    final_lgb.fit(X_full_train, y_full_train)
    lgb_test_returns = final_lgb.predict(X_test)
    lgb_ret_mae = mean_absolute_error(y_test, lgb_test_returns)

    best_rf.update({'random_state': 42, 'n_jobs': -1})
    final_rf = RandomForestRegressor(**best_rf)
    final_rf.fit(X_full_train, y_full_train)
    rf_test_returns = final_rf.predict(X_test)
    rf_ret_mae = mean_absolute_error(y_test, rf_test_returns)

    # -- 6. Save comparison ---------------------------------------------------
    results = pd.DataFrame({
        'Model'                : ['XGBoost (Tuned)', 'LightGBM (Tuned)', 'Random Forest (Tuned)'],
        'Val MAE (Return)'     : [study_xgb.best_value, study_lgb.best_value, study_rf.best_value],
        'Test MAE (Return, Jan 2026)': [xgb_ret_mae, lgb_ret_mae, rf_ret_mae],
        'Best Params'          : [str(best_xgb), str(best_lgb), str(best_rf)],
    })
    csv_path = os.path.join(results_dir, "tuning_comparison.csv")
    results.to_csv(csv_path, index=False)
    print(f"\n{results[['Model','Val MAE (Return)','Test MAE (Return, Jan 2026)']].to_string(index=False)}")
    print(f"\nSaved to {csv_path}")


if __name__ == "__main__":
    main()
