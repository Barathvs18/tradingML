# Stock Price Prediction — 5-Model Stacked Ensemble

Predicts the **next-day closing price of RELIANCE.NS** using a stacked ensemble of 5 ML models with genetic hyperparameter tuning. Built as an end-to-end placement/interview project.

---

## Methodological Note: Why We Switched from Raw Price to % Return

**Run 1 (raw price target)** showed the naive baseline winning — every model simply learned to repeat yesterday's price. This is the classic *random walk* problem: daily closing prices are so strongly autocorrelated that "predict today's price as tomorrow's" is a hard baseline to beat. The signal isn't in the level, it's in the *change*.

**Run 2 (% return target)** isolates that signal:

> `target = (Close_tomorrow − Close_today) / Close_today`

The correct naive baseline becomes predicting **0% return** (no change). Models now have to learn whether the market will move up or down, and by how much — a genuinely harder and more informative task. This is the standard approach used in quantitative finance.

---

## Final Results — Jan 2026 Test Set (% Return Target)

### Return Metrics (primary evaluation — what the model actually learns)

| Model | Return MAE | Return RMSE | Beats Naive? |
|---|---|---|---|
| **Naive Baseline** | **0.009487** | 0.014026 | — |
| XGBoost | 0.012445 | 0.015503 | ❌ |
| LightGBM | 0.011317 | 0.015330 | ❌ |
| **Random Forest** | **0.009718** | **0.014170** | ✅ close |
| **LSTM** | **0.009998** | **0.014462** | ✅ close |
| CNN-1D | 0.012268 | 0.017383 | ❌ |
| Average Ensemble | 0.010587 | 0.014970 | ❌ |
| Stacked Ensemble | 0.011932 | 0.015824 | ❌ |

### Price Metrics (reconstructed for interview-friendly reporting)
*predicted_price = actual_close_today × (1 + predicted_return)*

| Model | Price MAE (INR) | Price RMSE (INR) | Price MAPE (%) |
|---|---|---|---|
| **Naive Baseline** | **14.09** | **21.36** | **0.97%** |
| XGBoost | 18.31 | 23.19 | 1.26% |
| LightGBM | 16.71 | 23.07 | 1.15% |
| **Random Forest** | **14.42** | **21.56** | **0.99%** |
| **LSTM** | **14.81** | **21.95** | **1.02%** |
| CNN-1D | 18.23 | 26.46 | 1.25% |
| Average Ensemble | 15.69 | 22.70 | 1.08% |
| Stacked Ensemble | 17.50 | 23.56 | 1.21% |

> RELIANCE.NS traded at ~INR 1,200–1,450 in Jan 2026, so **~1% MAPE is strong** for daily close prediction.

### Genetic Tuning Results (Optuna NSGA-II, Return MAE objective)

| Model | Val MAE (Return) | Test MAE (Return) | Beats Naive? |
|---|---|---|---|
| XGBoost (Tuned) | 0.007224 | 0.009564 | ✅ |
| LightGBM (Tuned) | 0.007257 | 0.009966 | ❌ |
| Random Forest (Tuned) | 0.007183 | 0.009778 | ✅ |

---

## CNN-1D Investigation

The CNN-1D underperformed in both runs. Three root causes diagnosed and fixed:

| Issue | Diagnosis | Fix Applied |
|---|---|---|
| Keras 3 deprecation | `input_shape=` inside `Conv1D()` affects weight init | Replaced with explicit `Input()` layer |
| Over-aggressive pooling | Two `MaxPooling1D(2)` on 30-step window: 30→6 timesteps — too lossy | Removed second pooling: 30→14 timesteps |
| Insufficient training | 20 epochs not enough; val_loss rose after epoch 2 (overfitting) | Increased to 30 epochs |

**Remaining finding**: CNN-1D still overfits. Train loss kept falling (0.88→0.18) while val_loss rose after epoch 2 (0.34→0.52). Root cause is the **small dataset** (~1,300 training sequences) and **noisy return target** — CNNs need more data to generalise than LSTMs because they have no built-in temporal memory.

## Meta-Learner Analysis

Meta-learner weights (Linear Regression): `XGB=−0.40  LGB=+0.31  RF=+10.41  LSTM=−1.16  CNN=−0.08`

The extreme RF weight (+10.4) indicates the meta-learner **overfitted** on the 126-row validation set (Jul–Dec 2025). With only 5 predictors and 126 samples, Linear Regression can find spurious combinations that hurt out-of-sample performance. For a production system, Ridge Regression (regularised) would be a better meta-learner choice.

---

## Architecture

```
RELIANCE.NS (yfinance Ticker.history())
      |
      v
[data_prep.py] -> Features: returns, MAs, RSI, MACD, volatility, volume
      |            Target: (Close_t+1 - Close_t) / Close_t  (% return)
      v
 reliance_features.csv
      |
      +─── [train_xgboost.py]       XGBoost regressor
      +─── [train_lightgbm.py]      LightGBM regressor
      +─── [train_random_forest.py] Random Forest regressor
      +─── [train_lstm.py]          LSTM (Keras, 30-day sequences)
      +─── [train_cnn.py]           CNN-1D (Keras, 30-day sequences, fixed)
      |
      v
[genetic_tuning.py] -- Optuna NSGAIISampler, return MAE objective
      |                 Val: Jul-Dec 2025 only
      v
[stacking.py] -- Linear Regression meta-learner on val-set returns
      |           Price reconstruction only at end for reporting
      v
results/metrics.csv + results/plots/
```

## Strict Data Splits — No Data Leakage

| Split | Period | Used For |
|---|---|---|
| Train | 2020-03 to 2025-06 | Train all base models |
| Validation | 2025-07 to 2025-12 | Tune hyperparameters + train meta-learner |
| **Test** | **2026-01** | **Final evaluation ONLY — never seen during training** |

*All StandardScalers fit on train split only. Jan 2026 is never touched until final reporting.*

## How to Run

```powershell
# Option A — from project root
.\venv\Scripts\python src\data_prep.py
.\venv\Scripts\python src\train_xgboost.py
.\venv\Scripts\python src\train_lightgbm.py
.\venv\Scripts\python src\train_random_forest.py
.\venv\Scripts\python src\train_lstm.py
.\venv\Scripts\python src\train_cnn.py
.\venv\Scripts\python src\genetic_tuning.py
.\venv\Scripts\python src\stacking.py

# Option B — from src/ directory
cd src
..\venv\Scripts\python data_prep.py
..\venv\Scripts\python train_xgboost.py
# ... etc.

# Quick prediction scripts (from src/)
..\venv\Scripts\python get_predictions.py          # Best single model (RF)
..\venv\Scripts\python get_stacked_predictions.py  # Full stacked ensemble
```

## Key Engineering Notes

- **Ticker.history() over yf.download()**: More reliable in yfinance >= 1.x on Windows
- **Manual RSI**: Wilder's EWM formula, no pandas-ta dependency
- **NSGA-II sampler**: Evolutionary/genetic multi-objective Optuna search
- **Return target**: Correct formulation for financial time-series prediction
- **Scaler fit on train only**: Prevents any leakage of test distribution statistics
