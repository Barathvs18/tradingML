# AlgoPredict / Indian Market Lab

React/TypeScript and FastAPI application for historical daily NSE analysis,
user-created strategy backtests, a paper wallet, indicator comparison, intraday
analysis, and virtual trading simulation.

## Run local research on Windows

Requires Python 3.11 and Node 22.12 or newer. From this project directory:

```powershell
.\start-local.ps1
```

Open http://127.0.0.1:8000/analyze. This mode uses SQLite, requires no account
or broker, and serves React from FastAPI on localhost. See
[INDIAN_ANALYZER.md](INDIAN_ANALYZER.md) for the model, data and daily API.

## Run the full app for development

```powershell
docker compose up -d --build
docker compose exec -T api python -m scripts.load_candles --dir data
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000/register and create an account. The frontend proxies
API requests to localhost:8000. Bundled daily data imports automatically; the
separate loader populates the intraday dashboard and simulator. To populate the
dated NIFTY research universe, run `python scripts/download_indian_data.py --allow-incomplete`
before starting the app. The source currently supports 49 modelable stocks; INFRATEL
does not have enough history for this model. Data ends April 2021 and does not
represent today's NIFTY 50 constituents.

## Production

[PRODUCTION.md](PRODUCTION.md) covers MongoDB configuration, persistence,
health checks and verification. For Vercel/Render, follow
[DEPLOY_VERCEL_RENDER.md](DEPLOY_VERCEL_RENDER.md).

```bash
cp .env.production.example .env.production
# Set your domain, MongoDB URL and random JWT signing key.
docker compose --env-file .env.production -f docker-compose.prod.yml config --quiet
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build --wait
```

Production rejects placeholder secrets, insecure cookies and unsafe origins/
hosts. No default accounts are created. Google sign-in is optional.

## Main components

| Component | Responsibility |
| --- | --- |
| `frontend/src` | React UI, charts, analysis/history/performance, virtual wallet |
| `app/main.py` | Authenticated FastAPI server |
| `app/local_main.py` | Local research server and static frontend |
| `app/analysis` | CSV validation, features, logistic regression, SQLite persistence |
| `app/analysis/strategies.py` | Long-only strategy signals and historical backtest calculations |
| `/strategies` | Saved SMA, RSI and chained RSI/MACD rules with historical performance metrics |
| `/portfolio` | Per-user paper cash, holdings, orders, P&L and opt-in leaderboard |
| `/compare` | Thirteen daily reference signals and a heuristic market-regime estimate |
| `app/algorithms` | Intraday technical indicators and custom model adapters |
| MongoDB | Users, refresh sessions, stocks and minute candles |
| Redis-compatible Key Value | Caches, OAuth codes and atomic request limits |
| Docker / Caddy / Nginx | Deployment, HTTPS proxy and static frontend |

## Checks

Install `requirements.lock` and `requirements-dev.txt` in an isolated Python
3.11 environment. Historical research tests run against isolated SQLite. The
legacy PostgreSQL integration test scaffold is retired after the MongoDB move;
the authenticated API flow still needs MongoDB-backed integration coverage.

```powershell
.venv-prod/Scripts/python.exe -m unittest discover -s analysis_tests -v
cd frontend
npm run lint
npm run test:unit
npm run build
npm run test:e2e
```

`npm run test:production` checks the built app through its HTTPS proxy.
GitHub Actions runs checks and image builds when this directory is the
repository root. Publishing remains an operator action.

## Prediction behavior

Bundled Reliance, TCS and Infosys history ends April 2021. The same provider offers
the dated 50-symbol research universe, with 49 stocks currently having enough data
for this model; INFRATEL is too short. That data also ends April 2021. Daily predictions use
current/past inputs and estimate the next trading session's direction: UP above
+0.5%, DOWN below -0.5%, SIDEWAYS between them. Holdout results and a majority-
class baseline remain visible. Application hardening does not certify accuracy.

The Strategies page supports moving-average, RSI and chained RSI/MACD rules, historical
backtests, win rate, drawdown and Sharpe metrics, plus an opt-in strategy marketplace.
The Paper portfolio has per-user cash and holdings, simulated market/limit/stop-loss/
take-profit orders, daily and weekly P&L, an opt-in pseudonymous leaderboard, scheduled
checks, in-app plus optional Slack/Discord webhook alerts and rate-limited public API keys. Algo comparison presents 13
daily reference signals. A WebSocket replays cached daily candles; no live feed is wired.
Historical simulations do not model taxes, slippage or live broker orders.

Legacy future candles are reproducible simulated paths. The virtual wallet
applies simulated trades to historical replay. The web app has no live-data
feed or broker execution; older broker scripts outside this app are separate.

The authenticated app now includes an Intraday screen and `POST /app/predict/intraday`
for 1, 5, 10, 15 or 30-minute indicator signals, using aggregated candles already
stored in MongoDB. It reports candle time and staleness and does not generate
synthetic future prices. This is not a live feed: connect a licensed broker/data
provider and ingest fresh minute candles before treating signals as current. The
bundled Nifty daily CSV files cannot power intraday predictions.
