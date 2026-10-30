# Indian Market Lab

A daily Indian-stock direction analyzer built into the existing React/FastAPI project.
The local version requires no broker account, API key, PostgreSQL, Redis or Docker.

## Run locally on Windows

From `stock_prediction_api`, run:

```powershell
.\start-local.ps1
```

Open **http://127.0.0.1:8000/analyze**. The script builds the frontend and serves it
from the same FastAPI process. To reuse an existing build, use `-SkipBuild`.
Python dependencies live in `.venv`; Node dependencies live in `frontend/node_modules`.
If an existing environment is missing dependencies, run:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-local.txt
```

Local research mode uses a single local identity and binds to localhost. In the
original full application (`app.main:app`), the same analysis routes require login
and separate uploaded datasets and prediction histories by authenticated user.
This local mode is intended for your computer; do not expose it as a multi-user service.

## App flow

1. Choose one of the bundled or imported stocks and a historical trading date.
2. Analyze after the selected session's close. Only current/past candles enter the features.
3. View UP / DOWN / SIDEWAYS estimates and probability scores.
4. Reveal the actual next trading session's candle, return and direction.
5. Visit History for saved comparisons and Model performance for chronological holdout results.
6. Import another daily NSE stock CSV to train an additional model locally.

Daily data forecasts the next **trading session**, including holiday/weekend gaps,
not a 15-minute move or the next calendar day. The direction uses close-to-close
return: UP above +0.5%, DOWN below -0.5%, SIDEWAYS between these thresholds.
No future candles are invented. The last available session has no outcome to reveal.

## Data and provenance

Bundled files in `data/indian_daily` initially contain daily Reliance, TCS and Infosys history,
ending **30 April 2021**. Run `python scripts/download_indian_data.py` to fetch the remaining
symbols in the dated 50-symbol research universe recorded in `data/nifty50_2021.json`
with `python scripts/download_indian_data.py --allow-incomplete`. The source's
INFRATEL history has fewer rows than this model requires, so the app can currently
train on 49 of those 50 symbols. That historical universe is not today's membership
and is not point-in-time membership history.
This is historical research, not current market data. Source: [Rohan Rao's NIFTY-50 Stock Market Data](https://www.kaggle.com/datasets/rohanrao/nifty50-stock-market-data),
compiled from NSE records. `sources.json` records names, sources, date ranges and original file hashes.
Only Date/Open/High/Low/Close/Volume from each equity-series CSV are used.

To download the same research files again:

```powershell
python scripts/download_indian_data.py
```

Uploads require 300–20,000 daily rows, a maximum size of 4 MB, unique `YYYY-MM-DD`
dates, valid OHLC bounds, positive prices and nonnegative integer volume:

```csv
date,open,high,low,close,volume
2020-01-01,1500,1520,1490,1510,2500000
```

Use a consistent price adjustment for corporate actions. The included research data
can contain splits and large price jumps. These remain in the evaluation and the
performance screen discloses their count. The current stock selection does not
represent a point-in-time index membership or a portfolio backtest.

## Model and validation

Logistic regression with training-only standardization uses 11 causal features:
1/5/20-session returns, 5/20-session moving-average distances, RSI, ATR as a fraction
of price, return volatility, volume ratio, opening gap and candle body return.

Roughly 70% of eligible earlier examples train the model; later examples form a
single untouched holdout. One boundary example is omitted so training outcomes
end before the first held-out input. Dates used for training are unavailable in the
analysis selector. The newest dataset session may be analyzed without a known outcome.

Metrics include accuracy, macro F1, class precision/recall, confusion matrix and a
baseline that always predicts the most frequent **training** class. Probabilities
are uncalibrated model estimates, not a measured likelihood of successful trading.
Indicator context describes the inputs; it is not causal model attribution.
Results do not establish profitability. Historical strategy backtests apply close-based
signals on the following session and report simulated fees, win rate, drawdown and Sharpe.
Paper orders use historical daily ranges and include a fixed simulated fee; they never
reach a broker. Chained rules support RSI, MACD, close and moving average conditions.
Revealed next-session outcomes are tracked against model versions. Falling below the
holdout baseline after 20 tracked predictions raises a retraining recommendation;
importing a new dataset retrains the model. There is no automatic download of current
data or self-directed retraining. Model parameters are stored as JSON, not executable
pickle files.

## Files and storage

| File | Responsibility |
| --- | --- |
| `app/local_main.py` | Local server, startup data import, static frontend and health endpoint |
| `app/analysis/model.py` | CSV validation, features, training, holdout evaluation and inference |
| `app/analysis/store.py` | SQLite datasets, model versions, predictions, strategies, paper trading and alerts |
| `app/analysis/routes.py` | Analysis, strategy, portfolio, automation, streaming and public API routes |
| `frontend/src/pages/Analyze.tsx` | Date/stock selection, chart, estimates and outcome reveal |
| `frontend/src/pages/PredictionHistory.tsx` | Saved estimates and revealed outcomes |
| `frontend/src/pages/ModelPerformance.tsx` | Holdout scores, baseline and data limitations |
| `frontend/src/components/ResearchShell.tsx` | Navigation, data import and access control |
| `frontend/src/lib/research.ts` | API client, response types and formatting |
| `scripts/download_indian_data.py` | Public historical-data downloader |
| `analysis_tests/test_analysis.py` | Leakage, data validation, ownership, persistence and API tests |

`research.sqlite3` is created automatically and ignored by Git. Set
`ANALYSIS_DB_PATH` to choose another local database path. Each imported dataset is
versioned. Saved predictions preserve the original model probabilities and actual
outcome snapshot when a new dataset is imported. Outcomes stay hidden from API
responses until the explicit reveal request.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/app/analysis/config` | Local/authenticated mode |
| GET | `/app/analysis/stocks` | Available datasets |
| GET | `/app/analysis/stocks/{symbol}/dates` | Permitted held-out dates |
| POST | `/app/analysis/predict` | `{ "symbol": "RELIANCE", "as_of": "2021-04-29" }` |
| GET | `/app/analysis/history` | Most recent 100 predictions for this user |
| POST | `/app/analysis/history/{id}/reveal` | Reveal the actual next-session outcome |
| GET | `/app/analysis/stocks/{symbol}/performance` | Model and baseline evaluation |
| POST | `/app/analysis/import?symbol=HDFCBANK` | Raw `text/csv` body; validate/train/import |
| GET | `/app/analysis/strategies` | List strategies saved by this user |
| POST | `/app/analysis/strategies` | Save an SMA crossover or RSI mean-reversion rule |
| POST | `/app/analysis/strategies/{id}/backtest` | Run a next-session-applied historical simulation |
| DELETE | `/app/analysis/strategies/{id}` | Delete a strategy owned by this user |
| PUT | `/app/analysis/strategies/{id}/publish` | Publish or unpublish a saved strategy |
| GET | `/app/analysis/marketplace` | List public strategies |
| POST | `/app/analysis/marketplace/{id}/clone` | Clone a published strategy into your workspace |
| GET | `/app/analysis/stocks/{symbol}/compare` | Compare 13 indicator-family reference signals and estimate a market regime |
| GET | `/app/analysis/paper` | Paper wallet, holdings, equity curve and recent orders |
| POST | `/app/analysis/paper/orders` | Place a historical market, limit, stop-loss or take-profit simulation |
| POST | `/app/analysis/paper/orders/{id}/process` | Check a pending order against another historical daily candle |
| GET | `/app/analysis/leaderboard` | View pseudonymous traders who opted into simulated-return ranking |
| GET/POST | `/app/analysis/automations` | Schedule saved rules to check newly cached candles at a chosen interval |
| GET | `/app/analysis/alerts` | View in-app alerts for changed strategy signals and simulated orders |
| PUT/DELETE | `/app/analysis/alerts/webhook` | Configure a Slack or Discord alert destination |
| POST | `/app/analysis/api-keys` | Create a public API key (secret is shown once) |
| POST | `/app/analysis/public/v1/predict` | Rate-limited prediction with `X-API-Key` authentication |
| POST | `/app/predict/intraday` | Authenticated indicator signal from stored 1/5/10/15/30-minute candles |

The intraday screen and endpoint use the original authenticated server's TimescaleDB
minute candles. They aggregate to 1/5/10/15/30-minute bars and return the latest
indicator signal, last stored price and candle age. A feed connector must ingest fresh
minute candles for these to be live; no NSE/broker market-feed credentials are included.
The older simulation UI is under `/simulate` in the original authenticated server. The
historical daily paper portfolio lives at `/portfolio`; simulated fills use selected
daily OHLC candles and include a 10 bps fee. No order reaches a broker.

## Verification

```powershell
.venv\Scripts\python.exe -m unittest discover -s analysis_tests -v
cd frontend
npm run build
npm run lint
npm run test:e2e
```

The four browser tests use installed Google Chrome in headless mode, an isolated
SQLite database and a temporary local server on port 8011. They verify analysis,
outcome reveal, history, performance, CSV upload and mobile layout. The backend
suite contains 14 checks and does not require PostgreSQL or Redis.
