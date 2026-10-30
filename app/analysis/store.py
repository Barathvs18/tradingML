"""SQLite persistence for local research datasets and per-user prediction history."""

import json
import hashlib
import secrets
import json as json_module
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
import os
import re
import sqlite3
import threading
import uuid
from collections import OrderedDict
from contextlib import contextmanager, closing
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import numpy as np

from app.analysis.model import canonical_json, direction, features, predict, read_daily_csv, train
from app.analysis.strategies import compare_indicators, current_target, run_backtest

ROOT = Path(__file__).resolve().parents[2]
try:
    _universe = json.loads((ROOT / "data" / "nifty50_2021.json").read_text(encoding="utf-8"))
    NAMES = {**_universe.get("stocks", {}), "RELIANCE": "Reliance Industries",
             "TCS": "Tata Consultancy Services", "INFY": "Infosys"}
except (OSError, ValueError, TypeError):
    NAMES = {"RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services", "INFY": "Infosys"}


class AnalysisStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self._cache = OrderedDict()
        self._training_lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS analysis_datasets (
                    owner TEXT NOT NULL, symbol TEXT NOT NULL, version TEXT NOT NULL,
                    name TEXT NOT NULL, source TEXT NOT NULL, rows_json TEXT NOT NULL,
                    model_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(owner, symbol, version)
                );
                CREATE TABLE IF NOT EXISTS analysis_predictions (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, symbol TEXT NOT NULL,
                    as_of TEXT NOT NULL, model_version TEXT NOT NULL,
                    result_json TEXT NOT NULL, outcome_json TEXT,
                    revealed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS analysis_predictions_owner_date
                    ON analysis_predictions(owner, created_at DESC);
                CREATE TABLE IF NOT EXISTS analysis_strategies (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
                    symbol TEXT NOT NULL, strategy_type TEXT NOT NULL,
                    parameters_json TEXT NOT NULL, initial_capital REAL NOT NULL,
                    transaction_cost_bps REAL NOT NULL, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analysis_strategy_shares (
                    strategy_id TEXT PRIMARY KEY, owner TEXT NOT NULL, published_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS analysis_strategies_owner_date
                    ON analysis_strategies(owner, created_at DESC);
                CREATE TABLE IF NOT EXISTS paper_accounts (
                    owner TEXT PRIMARY KEY, starting_balance REAL NOT NULL, cash REAL NOT NULL,
                    realized_pnl REAL NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS paper_positions (
                    owner TEXT NOT NULL, symbol TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0,
                    average_price REAL NOT NULL DEFAULT 0, realized_pnl REAL NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL, PRIMARY KEY(owner, symbol)
                );
                CREATE TABLE IF NOT EXISTS paper_orders (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, symbol TEXT NOT NULL,
                    side TEXT NOT NULL, order_type TEXT NOT NULL, quantity INTEGER NOT NULL,
                    trigger_price REAL, requested_date TEXT NOT NULL, status TEXT NOT NULL,
                    fill_price REAL, realized_pnl REAL NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, filled_at TEXT
                );
                CREATE INDEX IF NOT EXISTS paper_orders_owner_date
                    ON paper_orders(owner, created_at DESC);
                CREATE TABLE IF NOT EXISTS paper_progress (
                    owner TEXT NOT NULL, symbol TEXT NOT NULL, last_date TEXT NOT NULL,
                    PRIMARY KEY(owner, symbol)
                );
                CREATE TABLE IF NOT EXISTS paper_preferences (
                    owner TEXT PRIMARY KEY, leaderboard_opt_in INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS analysis_automations (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, strategy_id TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL, quantity INTEGER NOT NULL,
                    auto_trade INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1,
                    last_checked_at TEXT, last_signal_date TEXT, last_target INTEGER,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS analysis_automations_owner ON analysis_automations(owner, enabled);
                CREATE TABLE IF NOT EXISTS analysis_alerts (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, automation_id TEXT,
                    message TEXT NOT NULL, details_json TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS analysis_alerts_owner_date ON analysis_alerts(owner, created_at DESC);
                CREATE TABLE IF NOT EXISTS analysis_alert_webhooks (
                    owner TEXT PRIMARY KEY, provider TEXT NOT NULL, webhook_url TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS analysis_public_api_keys (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, key_hash TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL, last_used_at TEXT
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_csv(self, symbol: str, raw: bytes, owner: str = "shared", source: str = "User-uploaded daily CSV") -> dict:
        symbol = symbol.strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9&.-]{0,19}", symbol):
            raise ValueError("Use a stock symbol of 1-20 letters, numbers, &, periods or hyphens.")
        frame = read_daily_csv(raw)
        # Training happens before the transaction: an invalid upload cannot replace a working dataset.
        if not self._training_lock.acquire(blocking=False):
            raise RuntimeError("Another dataset is being trained. Retry in a few seconds.")
        try:
            model = train(frame)
        finally:
            self._training_lock.release()
        rows_json = canonical_json(frame.to_dict("records"))
        with self._lock, self.connect() as db:
            if owner != "shared":
                symbols = db.execute("SELECT COUNT(DISTINCT symbol) FROM analysis_datasets WHERE owner=?", (owner,)).fetchone()[0]
                existing = db.execute("SELECT 1 FROM analysis_datasets WHERE owner=? AND symbol=?", (owner, symbol)).fetchone()
                if symbols >= 20 and not existing:
                    raise ValueError("This workspace supports at most 20 imported symbols.")
                used = db.execute("SELECT COALESCE(SUM(length(rows_json)),0) FROM analysis_datasets "
                                  "WHERE owner=? AND NOT (symbol=? AND version=?)", (owner, symbol, model["version"])).fetchone()[0]
                if used + len(rows_json) > 50_000_000:
                    raise ValueError("This workspace has reached its 50 MB dataset storage limit.")
            db.execute("""INSERT INTO analysis_datasets VALUES(?,?,?,?,?,?,?,?)
                       ON CONFLICT(owner,symbol,version) DO UPDATE SET created_at=excluded.created_at""",
                       (owner, symbol, model["version"], NAMES.get(symbol, symbol), source,
                        rows_json, canonical_json(model),
                        datetime.now(timezone.utc).isoformat()))
            self._cache[(owner, symbol, model["version"])] = (frame, model, features(frame))
            db.execute("DELETE FROM analysis_datasets WHERE owner=? AND symbol=? AND version NOT IN "
                       "(SELECT version FROM analysis_datasets WHERE owner=? AND symbol=? ORDER BY created_at DESC LIMIT 5)",
                       (owner, symbol, owner, symbol))
            self._trim_cache()
        return self.stock(owner, symbol)

    def bootstrap(self, directory: Path | None = None):
        directory = directory or ROOT / "data" / "indian_daily"
        manifest_path = directory / "sources.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
        for path in sorted(directory.glob("*.csv")):
            symbol = path.stem.upper()
            raw = path.read_bytes()
            frame = read_daily_csv(raw)
            import hashlib
            digest = hashlib.sha256(frame.to_csv(index=False).encode()).hexdigest()
            with self.connect() as db:
                exists = db.execute("SELECT 1 FROM analysis_datasets WHERE owner='shared' AND symbol=? "
                                    "AND json_extract(model_json,'$.dataset_sha256')=?", (symbol, digest)).fetchone()
            if not exists:
                self.import_csv(symbol, raw, source=manifest.get(symbol, {}).get("source", "Bundled daily research CSV"))

    def _dataset(self, owner: str, symbol: str):
        with self.connect() as db:
            row = db.execute("""SELECT * FROM analysis_datasets WHERE symbol=? AND owner IN (?, 'shared')
                             ORDER BY CASE WHEN owner=? THEN 0 ELSE 1 END, created_at DESC LIMIT 1""",
                             (symbol.upper(), owner, owner)).fetchone()
        if row is None:
            raise LookupError("No daily data for this symbol. Import an Indian-stock CSV first.")
        key = (row["owner"], row["symbol"], row["version"])
        with self._lock:
            if key not in self._cache:
                frame = pd.DataFrame(json.loads(row["rows_json"]))
                self._cache[key] = (frame, json.loads(row["model_json"]), features(frame))
            frame, model, matrix = self._cache[key]
            self._cache.move_to_end(key)
            self._trim_cache()
        return row, frame, model, matrix

    def _trim_cache(self):
        while len(self._cache) > 8:
            self._cache.popitem(last=False)

    def health(self):
        with self.connect() as db:
            db.execute("SELECT COUNT(*) FROM analysis_datasets").fetchone()

    def backup(self, target: Path):
        """SQLite's online backup API also copies committed WAL contents safely."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as source, closing(sqlite3.connect(target)) as destination:
            source.backup(destination)

    def stock(self, owner: str, symbol: str) -> dict:
        row, frame, model, _ = self._dataset(owner, symbol)
        return {"symbol": row["symbol"], "name": row["name"], "exchange": "NSE", "currency": "INR",
                "interval": "1d", "rows": len(frame), "start": str(frame["date"].iloc[0]),
                "end": str(frame["date"].iloc[-1]), "analysis_start": model["report"]["test_start"],
                "source": row["source"], "model_version": model["version"]}

    def stocks(self, owner: str) -> list:
        with self.connect() as db:
            symbols = [row[0] for row in db.execute("SELECT DISTINCT symbol FROM analysis_datasets "
                                                  "WHERE owner IN (?, 'shared') ORDER BY symbol", (owner,))]
        return [self.stock(owner, symbol) for symbol in symbols]

    def dates(self, owner: str, symbol: str) -> list:
        _, frame, model, _ = self._dataset(owner, symbol)
        return frame.loc[frame["date"] >= model["report"]["test_start"], "date"].tolist()[::-1]

    def analyze(self, owner: str, symbol: str, as_of: str) -> dict:
        dataset, frame, model, matrix = self._dataset(owner, symbol)
        matches = frame.index[frame["date"] == as_of]
        if len(matches) != 1:
            raise ValueError("Select a trading date available in this dataset.")
        index = int(matches[0])
        if as_of < model["report"]["test_start"]:
            raise ValueError("Select a date after training ended to keep the comparison on unseen data.")
        latest = frame.iloc[index]
        row = matrix.iloc[index]
        estimate = predict(model, row)
        history = frame.iloc[max(0, index - 89):index + 1]
        candles = [{"time": int(pd.Timestamp(f"{record.date}T15:30:00", tz="Asia/Kolkata").timestamp()),
                    "open": float(record.open), "high": float(record.high), "low": float(record.low),
                    "close": float(record.close), "volume": int(record.volume)} for record in history.itertuples()]
        sma = frame["close"].rolling(20).mean()
        overlay = [{"time": candle["time"], "value": float(sma.iloc[position])}
                   for candle, position in zip(candles, history.index) if pd.notna(sma.iloc[position])]
        context = [f"Close is {abs(row.ma_20_distance) * 100:.2f}% {'above' if row.ma_20_distance >= 0 else 'below'} its 20-session average.",
                   f"RSI is {row.rsi_14:.1f}; {'oversold' if row.rsi_14 < 30 else 'overbought' if row.rsi_14 > 70 else 'in the middle range'}.",
                   f"Volume is {row.volume_ratio_20:.2f} times its 20-session average."]
        outcome = None
        if index + 1 < len(frame):
            following = frame.iloc[index + 1]
            change = float(following["close"] / latest["close"] - 1)
            actual = direction(change, model["threshold"])
            outcome = {"date": str(following["date"]), "close": float(following["close"]),
                       "return_pct": change * 100, "direction": actual, "correct": actual == estimate["direction"],
                       "candle": {"time": int(pd.Timestamp(f"{following['date']}T15:30:00", tz="Asia/Kolkata").timestamp()),
                                  "open": float(following["open"]), "high": float(following["high"]),
                                  "low": float(following["low"]), "close": float(following["close"]),
                                  "volume": int(following["volume"])}}
        result = {"id": str(uuid.uuid4()), "symbol": dataset["symbol"], "name": dataset["name"],
                  "as_of": as_of, "horizon": "Next trading session, close to close", "close": float(latest["close"]),
                  **estimate, "threshold_pct": model["threshold"] * 100, "model_version": model["version"],
                  "training_end": model["report"]["training_outcomes_end"], "history": candles,
                  "overlays": {"20-session average": overlay}, "context": context,
                  "indicators": {"rsi": float(row.rsi_14), "volume_ratio": float(row.volume_ratio_20),
                                 "volatility_pct": float(row.volatility_20) * 100},
                  "outcome_available": outcome is not None, "outcome": None,
                  "created_at": datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute("INSERT INTO analysis_predictions VALUES(?,?,?,?,?,?,?,?,?)",
                       (result["id"], owner, result["symbol"], as_of, model["version"], canonical_json(result),
                        canonical_json(outcome) if outcome else None, 0, result["created_at"]))
        return result

    def history(self, owner: str, limit: int = 100) -> list:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM analysis_predictions WHERE owner=? ORDER BY created_at DESC LIMIT ?",
                              (owner, limit)).fetchall()
        result = []
        for row in rows:
            item = json.loads(row["result_json"])
            item.pop("history", None)
            item.pop("overlays", None)
            item["outcome"] = json.loads(row["outcome_json"]) if row["revealed"] and row["outcome_json"] else None
            result.append(item)
        return result

    def reveal(self, owner: str, prediction_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT outcome_json FROM analysis_predictions WHERE id=? AND owner=?",
                             (prediction_id, owner)).fetchone()
            if row is None:
                raise LookupError("Prediction not found.")
            if not row["outcome_json"]:
                return {"available": False, "outcome": None,
                        "message": "The dataset ends on this date. There is no next-session candle to reveal."}
            db.execute("UPDATE analysis_predictions SET revealed=1 WHERE id=? AND owner=?", (prediction_id, owner))
            return {"available": True, "outcome": json.loads(row["outcome_json"])}

    def performance(self, owner: str, symbol: str) -> dict:
        dataset, frame, model, _ = self._dataset(owner, symbol)
        with self.connect() as db:
            feedback = db.execute("SELECT result_json,outcome_json FROM analysis_predictions "
                "WHERE owner=? AND symbol=? AND revealed=1 AND outcome_json IS NOT NULL", (owner, symbol.upper())).fetchall()
        correct = sum(json.loads(row["result_json"])["direction"] == json.loads(row["outcome_json"])["direction"]
                      for row in feedback)
        feedback_accuracy = correct / len(feedback) if feedback else None
        return {"symbol": dataset["symbol"], "name": dataset["name"], "model_version": model["version"],
                "model_type": "Logistic regression", "threshold_pct": model["threshold"] * 100,
                "source": dataset["source"], "dataset_start": frame["date"].iloc[0], "dataset_end": frame["date"].iloc[-1],
                "features": model["feature_names"], "tracked_predictions": len(feedback),
                "tracked_accuracy": feedback_accuracy,
                "retrain_recommended": len(feedback) >= 20 and feedback_accuracy < model["report"]["baseline_accuracy"],
                **model["report"]}

    def compare_algorithms(self, owner: str, symbol: str) -> dict:
        _, frame, _, _ = self._dataset(owner, symbol)
        return compare_indicators(frame)

    def create_strategy(self, owner: str, payload: dict) -> dict:
        name = str(payload["name"]).strip()
        if not name or len(name) > 60:
            raise ValueError("Strategy name must contain 1-60 characters.")
        symbol = str(payload["symbol"]).strip().upper()
        self._dataset(owner, symbol)
        kind = payload["strategy_type"]
        parameters = payload["parameters"]
        initial_capital = float(payload["initial_capital"])
        transaction_cost_bps = float(payload["transaction_cost_bps"])
        if not np.isfinite(initial_capital) or not 1_000 <= initial_capital <= 1_000_000_000:
            raise ValueError("Initial capital must be between ₹1,000 and ₹1,000,000,000.")
        if not np.isfinite(transaction_cost_bps) or not 0 <= transaction_cost_bps <= 100:
            raise ValueError("Transaction cost must be between 0 and 100 basis points.")
        # Validate rule names/ranges before saving the strategy.
        if kind == "sma_crossover":
            if set(parameters) != {"short_window", "long_window"}:
                raise ValueError("SMA strategies need short_window and long_window parameters.")
            short_window, long_window = int(parameters["short_window"]), int(parameters["long_window"])
            if not 2 <= short_window < long_window <= 250:
                raise ValueError("SMA windows must satisfy 2 <= short < long <= 250.")
            parameters = {"short_window": short_window, "long_window": long_window}
        elif kind == "rsi_reversion":
            if set(parameters) != {"oversold", "overbought"}:
                raise ValueError("RSI strategies need oversold and overbought parameters.")
            oversold, overbought = int(parameters["oversold"]), int(parameters["overbought"])
            if not 5 <= oversold <= 45 or not 55 <= overbought <= 95 or oversold >= overbought:
                raise ValueError("RSI levels must have oversold 5-45 below overbought 55-95.")
            parameters = {"oversold": oversold, "overbought": overbought}
        elif kind == "rule_chain":
            indicator_names = {"close", "rsi_14", "macd_line", "macd_signal", "sma_5", "sma_20", "sma_50"}
            if set(parameters) != {"entry_logic", "exit_logic", "entry_conditions", "exit_conditions"}:
                raise ValueError("Rule chains need entry/exit logic and condition lists.")
            if parameters["entry_logic"] not in {"AND", "OR"} or parameters["exit_logic"] not in {"AND", "OR"}:
                raise ValueError("Condition logic must be AND or OR.")
            normalized = {}
            for group in ("entry_conditions", "exit_conditions"):
                conditions = parameters[group]
                if not isinstance(conditions, list) or not 1 <= len(conditions) <= 4:
                    raise ValueError("Each entry and exit rule needs 1-4 conditions.")
                clean_conditions = []
                for condition in conditions:
                    if not isinstance(condition, dict) or condition.get("left") not in indicator_names:
                        raise ValueError("Choose a supported indicator for each condition.")
                    operator = condition.get("operator")
                    if operator not in {"<", ">", "crosses_above", "crosses_below"}:
                        raise ValueError("Choose a supported comparison operator.")
                    if operator.startswith("crosses_"):
                        if condition.get("right") not in indicator_names or "value" in condition:
                            raise ValueError("Crossover rules must compare two indicators.")
                        clean_conditions.append({"left": condition["left"], "operator": operator,
                                                 "right": condition["right"]})
                    else:
                        if condition.get("right") is not None or set(condition) != {"left", "operator", "value"}:
                            raise ValueError("Threshold rules need one numeric value.")
                        value = float(condition["value"])
                        if not np.isfinite(value):
                            raise ValueError("Rule thresholds must be finite numbers.")
                        clean_conditions.append({"left": condition["left"], "operator": operator, "value": value})
                normalized[group] = clean_conditions
            parameters = {"entry_logic": parameters["entry_logic"], "exit_logic": parameters["exit_logic"], **normalized}
        else:
            raise ValueError("Choose a supported strategy type.")
        created_at = datetime.now(timezone.utc).isoformat()
        strategy = {"id": str(uuid.uuid4()), "owner": owner, "name": name, "symbol": symbol,
                    "strategy_type": kind, "parameters": parameters, "initial_capital": initial_capital,
                    "transaction_cost_bps": transaction_cost_bps, "created_at": created_at}
        with self.connect() as db:
            db.execute("INSERT INTO analysis_strategies VALUES(?,?,?,?,?,?,?,?,?)",
                       (strategy["id"], owner, name, symbol, kind, canonical_json(parameters),
                        initial_capital, transaction_cost_bps, created_at))
        strategy.pop("owner")
        return strategy

    @staticmethod
    def _strategy(row: sqlite3.Row) -> dict:
        return {"id": row["id"], "name": row["name"], "symbol": row["symbol"],
                "strategy_type": row["strategy_type"], "parameters": json.loads(row["parameters_json"]),
                "initial_capital": row["initial_capital"],
                "transaction_cost_bps": row["transaction_cost_bps"], "created_at": row["created_at"]}

    def strategies(self, owner: str) -> list:
        with self.connect() as db:
            rows = db.execute("SELECT s.*, (sh.strategy_id IS NOT NULL) AS published FROM analysis_strategies s "
                              "LEFT JOIN analysis_strategy_shares sh ON sh.strategy_id=s.id "
                              "WHERE s.owner=? ORDER BY s.created_at DESC LIMIT 100",
                              (owner,)).fetchall()
        return [{**self._strategy(row), "published": bool(row["published"])} for row in rows]

    def delete_strategy(self, owner: str, strategy_id: str) -> dict:
        with self.connect() as db:
            cursor = db.execute("DELETE FROM analysis_strategies WHERE id=? AND owner=?", (strategy_id, owner))
            if cursor.rowcount == 0:
                raise LookupError("Strategy not found.")
        return {"deleted": True, "id": strategy_id}

    def publish_strategy(self, owner: str, strategy_id: str, published: bool) -> dict:
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM analysis_strategies WHERE id=? AND owner=?", (strategy_id, owner)).fetchone()
            if exists is None:
                raise LookupError("Strategy not found.")
            if published:
                db.execute("INSERT INTO analysis_strategy_shares VALUES(?,?,?) ON CONFLICT(strategy_id) DO UPDATE SET "
                           "published_at=excluded.published_at", (strategy_id, owner, datetime.now(timezone.utc).isoformat()))
            else:
                db.execute("DELETE FROM analysis_strategy_shares WHERE strategy_id=? AND owner=?", (strategy_id, owner))
        return {"id": strategy_id, "published": published}

    def marketplace_strategies(self, limit: int = 50) -> list:
        with self.connect() as db:
            rows = db.execute("SELECT s.*, sh.owner AS publisher FROM analysis_strategies s "
                "JOIN analysis_strategy_shares sh ON sh.strategy_id=s.id "
                "ORDER BY sh.published_at DESC LIMIT ?", (limit,)).fetchall()
        return [{**self._strategy(row), "published": True,
                 "publisher": f"Trader {hashlib.sha256(row['publisher'].encode()).hexdigest()[:6].upper()}"}
                for row in rows]

    def clone_strategy(self, owner: str, strategy_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT s.* FROM analysis_strategies s JOIN analysis_strategy_shares sh "
                             "ON sh.strategy_id=s.id WHERE s.id=?", (strategy_id,)).fetchone()
        if row is None:
            raise LookupError("Published strategy not found.")
        source = self._strategy(row)
        name = f"Clone of {source['name']}"[:60]
        payload = {"name": name, "symbol": source["symbol"], "strategy_type": source["strategy_type"],
                   "parameters": source["parameters"], "initial_capital": source["initial_capital"],
                   "transaction_cost_bps": source["transaction_cost_bps"]}
        return self.create_strategy(owner, payload)

    def backtest_strategy(self, owner: str, strategy_id: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT * FROM analysis_strategies WHERE id=? AND owner=?", (strategy_id, owner)).fetchone()
        if row is None:
            raise LookupError("Strategy not found.")
        strategy = self._strategy(row)
        dataset, frame, _, _ = self._dataset(owner, strategy["symbol"])
        result = run_backtest(frame, strategy["strategy_type"], strategy["parameters"],
                              strategy["initial_capital"], strategy["transaction_cost_bps"])
        return {"strategy": strategy, "stock_name": dataset["name"], "data_source": dataset["source"], **result}

    def _ensure_paper_account(self, owner: str):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO paper_accounts(owner,starting_balance,cash,realized_pnl,updated_at) "
                       "VALUES(?,1000000,1000000,0,?)", (owner, datetime.now(timezone.utc).isoformat()))

    def paper_account(self, owner: str) -> dict:
        self._ensure_paper_account(owner)
        with self.connect() as db:
            account = db.execute("SELECT * FROM paper_accounts WHERE owner=?", (owner,)).fetchone()
            preference = db.execute("SELECT leaderboard_opt_in FROM paper_preferences WHERE owner=?", (owner,)).fetchone()
            rows = db.execute("SELECT * FROM paper_positions WHERE owner=? AND quantity<>0 ORDER BY symbol", (owner,)).fetchall()
            orders = db.execute("SELECT * FROM paper_orders WHERE owner=? ORDER BY created_at DESC LIMIT 50", (owner,)).fetchall()
            fills = db.execute("SELECT * FROM paper_orders WHERE owner=? AND status='filled' ORDER BY filled_at,created_at",
                               (owner,)).fetchall()
        holdings = []
        market_value = unrealized_pnl = 0.0
        for row in rows:
            dataset, frame, _, _ = self._dataset(owner, row["symbol"])
            price = float(frame.iloc[-1]["close"])
            value = row["quantity"] * price
            pnl = row["quantity"] * (price - row["average_price"])
            market_value += value
            unrealized_pnl += pnl
            holdings.append({"symbol": row["symbol"], "name": dataset["name"], "quantity": row["quantity"],
                             "average_price": row["average_price"], "last_price": price,
                             "market_value": value, "unrealized_pnl": pnl, "realized_pnl": row["realized_pnl"]})
        total_equity = float(account["cash"]) + market_value
        curve = self._paper_equity_curve(owner, float(account["starting_balance"]), fills)
        return {"starting_balance": account["starting_balance"], "cash": account["cash"],
                "market_value": market_value, "equity": total_equity,
                "realized_pnl": account["realized_pnl"], "unrealized_pnl": unrealized_pnl,
                "total_pnl": total_equity - account["starting_balance"],
                "return_pct": (total_equity / account["starting_balance"] - 1) * 100,
                "leaderboard_opt_in": bool(preference["leaderboard_opt_in"]) if preference else False,
                "holdings": holdings, "orders": [dict(row) for row in orders], "equity_curve": curve}

    def _paper_equity_curve(self, owner: str, starting_balance: float, fills) -> list:
        if not fills:
            return []
        symbols = sorted({row["symbol"] for row in fills})
        market_data = {}
        calendar = set()
        for symbol in symbols:
            _, frame, _, _ = self._dataset(owner, symbol)
            market_data[symbol] = frame
            calendar.update(frame["date"].astype(str).tolist())
        first_date = min(row["filled_at"] for row in fills)
        last_date = max(frame["date"].iloc[-1] for frame in market_data.values())
        dates = sorted(day for day in calendar if first_date <= day <= last_date)[-750:]
        events = iter(fills)
        event = next(events, None)
        cash = starting_balance
        positions = {}
        last_prices = {}
        indexes = {symbol: 0 for symbol in symbols}
        result = []
        for day in dates:
            while event is not None and event["filled_at"] <= day:
                amount = int(event["quantity"])
                price = float(event["fill_price"])
                fee = price * amount * 0.001
                if event["side"] == "BUY":
                    cash -= price * amount + fee
                    positions[event["symbol"]] = positions.get(event["symbol"], 0) + amount
                else:
                    cash += price * amount - fee
                    positions[event["symbol"]] = positions.get(event["symbol"], 0) - amount
                event = next(events, None)
            for symbol, frame in market_data.items():
                index = indexes[symbol]
                while index < len(frame) and str(frame.iloc[index]["date"]) <= day:
                    last_prices[symbol] = float(frame.iloc[index]["close"])
                    index += 1
                indexes[symbol] = index
            equity = cash + sum(quantity * last_prices.get(symbol, 0.0)
                                for symbol, quantity in positions.items() if quantity > 0)
            result.append({"date": day, "equity": round(equity, 2),
                           "daily_pnl": round(equity - result[-1]["equity"], 2) if result else round(equity - starting_balance, 2)})
        return result

    def paper_dates(self, owner: str, symbol: str) -> list:
        _, frame, _, _ = self._dataset(owner, symbol)
        return frame["date"].astype(str).tolist()

    def stream_candles(self, symbol: str, limit: int = 250, from_date: str | None = None) -> list:
        _, frame, _, _ = self._dataset("local", symbol)
        if from_date:
            frame = frame.loc[frame["date"] >= from_date]
        frame = frame.tail(max(1, min(int(limit), 1000)))
        return [{"date": str(row.date), "open": float(row.open), "high": float(row.high),
                 "low": float(row.low), "close": float(row.close), "volume": int(row.volume)}
                for row in frame.itertuples()]

    @staticmethod
    def _order_fill_price(order: dict, candle: dict) -> float | None:
        kind, side, trigger = order["order_type"], order["side"], order["trigger_price"]
        if kind == "market":
            return float(candle["close"])
        if kind == "limit":
            if side == "BUY" and candle["low"] <= trigger:
                return float(min(candle["open"], trigger))
            if side == "SELL" and candle["high"] >= trigger:
                return float(max(candle["open"], trigger))
        elif kind == "stop_loss" and candle["low"] <= trigger:
            return float(min(candle["open"], trigger))
        elif kind == "take_profit" and candle["high"] >= trigger:
            return float(max(candle["open"], trigger))
        return None

    def _apply_paper_fill(self, db, order: dict, candle: dict):
        price = self._order_fill_price(order, candle)
        if price is None:
            return False
        account = db.execute("SELECT * FROM paper_accounts WHERE owner=?", (order["owner"],)).fetchone()
        position = db.execute("SELECT * FROM paper_positions WHERE owner=? AND symbol=?",
                              (order["owner"], order["symbol"])).fetchone()
        old_quantity = int(position["quantity"]) if position else 0
        average = float(position["average_price"]) if position else 0.0
        fee = price * order["quantity"] * 0.001  # 10 bps simulated trading cost
        if order["side"] == "BUY":
            required = price * order["quantity"] + fee
            if required > account["cash"]:
                raise ValueError("Insufficient paper cash to fill this order.")
            quantity = old_quantity + order["quantity"]
            average = (old_quantity * average + order["quantity"] * price) / quantity
            cash_delta = -required
            realized = 0.0
        else:
            if order["quantity"] > old_quantity:
                raise ValueError("Sell quantity cannot exceed the paper holding.")
            quantity = old_quantity - order["quantity"]
            realized = (price - average) * order["quantity"] - fee
            cash_delta = price * order["quantity"] - fee
            if quantity == 0:
                average = 0.0
        now = datetime.now(timezone.utc).isoformat()
        db.execute("INSERT INTO paper_positions VALUES(?,?,?,?,?,?) ON CONFLICT(owner,symbol) DO UPDATE SET "
                   "quantity=excluded.quantity,average_price=excluded.average_price,"
                   "realized_pnl=paper_positions.realized_pnl+excluded.realized_pnl,updated_at=excluded.updated_at",
                   (order["owner"], order["symbol"], quantity, average, realized, now))
        db.execute("UPDATE paper_accounts SET cash=cash+?,realized_pnl=realized_pnl+?,updated_at=? WHERE owner=?",
                   (cash_delta, realized, now, order["owner"]))
        db.execute("UPDATE paper_orders SET status='filled',fill_price=?,realized_pnl=?,filled_at=? WHERE id=?",
                   (price, realized, order["requested_date"], order["id"]))
        return True

    def place_paper_order(self, owner: str, payload: dict) -> dict:
        symbol = str(payload["symbol"]).strip().upper()
        date = str(payload["as_of"])
        side, kind, quantity = payload["side"], payload["order_type"], int(payload["quantity"])
        trigger = payload.get("trigger_price")
        if not 1 <= quantity <= 1_000_000:
            raise ValueError("Order quantity must be between 1 and 1,000,000 shares.")
        if kind not in {"market", "limit", "stop_loss", "take_profit"} or side not in {"BUY", "SELL"}:
            raise ValueError("Unsupported paper order type or side.")
        if kind in {"limit", "stop_loss", "take_profit"} and (trigger is None or not np.isfinite(float(trigger)) or float(trigger) <= 0):
            raise ValueError("This order type needs a positive trigger price.")
        if kind in {"stop_loss", "take_profit"} and side != "SELL":
            raise ValueError("Stop-loss and take-profit orders currently close long holdings only.")
        _, frame, _, _ = self._dataset(owner, symbol)
        matches = frame.index[frame["date"] == date]
        if len(matches) != 1:
            raise ValueError("Choose a trading date available in this historical dataset.")
        row = frame.iloc[int(matches[0])]
        candle = {key: float(row[key]) for key in ("open", "high", "low", "close")}
        self._ensure_paper_account(owner)
        order = {"id": str(uuid.uuid4()), "owner": owner, "symbol": symbol, "side": side, "order_type": kind,
                 "quantity": quantity, "trigger_price": float(trigger) if trigger is not None else None,
                 "requested_date": date, "status": "pending", "fill_price": None, "realized_pnl": 0.0,
                 "created_at": datetime.now(timezone.utc).isoformat(), "filled_at": None}
        with self.connect() as db:
            progress = db.execute("SELECT last_date FROM paper_progress WHERE owner=? AND symbol=?", (owner, symbol)).fetchone()
            if progress and date < progress["last_date"]:
                raise ValueError(f"Historical order dates must move forward from {progress['last_date']}.")
            db.execute("INSERT INTO paper_orders VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (order["id"], owner, symbol, side, kind, quantity, order["trigger_price"], date,
                        "pending", None, 0.0, order["created_at"], None))
            order["status"] = "filled" if self._apply_paper_fill(db, order, candle) else "pending"
            db.execute("INSERT INTO paper_progress VALUES(?,?,?) ON CONFLICT(owner,symbol) DO UPDATE SET "
                       "last_date=MAX(paper_progress.last_date,excluded.last_date)", (owner, symbol, date))
            saved = db.execute("SELECT * FROM paper_orders WHERE id=?", (order["id"],)).fetchone()
        return dict(saved)

    def process_paper_order(self, owner: str, order_id: str, as_of: str) -> dict:
        with self.connect() as db:
            saved = db.execute("SELECT * FROM paper_orders WHERE id=? AND owner=?", (order_id, owner)).fetchone()
        if saved is None:
            raise LookupError("Paper order not found.")
        if saved["status"] != "pending":
            raise ValueError("Only pending orders can be processed.")
        if as_of < saved["requested_date"]:
            raise ValueError("Order processing date cannot be earlier than its creation date.")
        _, frame, _, _ = self._dataset(owner, saved["symbol"])
        matches = frame.index[frame["date"] == as_of]
        if len(matches) != 1:
            raise ValueError("Choose a trading date available in this historical dataset.")
        row = frame.iloc[int(matches[0])]
        candle = {key: float(row[key]) for key in ("open", "high", "low", "close")}
        order = dict(saved)
        order["requested_date"] = as_of
        with self.connect() as db:
            progress = db.execute("SELECT last_date FROM paper_progress WHERE owner=? AND symbol=?",
                                  (owner, saved["symbol"])).fetchone()
            if progress and as_of < progress["last_date"]:
                raise ValueError(f"Historical order dates must move forward from {progress['last_date']}.")
            order["status"] = "filled" if self._apply_paper_fill(db, order, candle) else "pending"
            db.execute("UPDATE paper_orders SET requested_date=? WHERE id=?", (as_of, order_id))
            db.execute("INSERT INTO paper_progress VALUES(?,?,?) ON CONFLICT(owner,symbol) DO UPDATE SET "
                       "last_date=MAX(paper_progress.last_date,excluded.last_date)", (owner, saved["symbol"], as_of))
            result = db.execute("SELECT * FROM paper_orders WHERE id=?", (order_id,)).fetchone()
        return dict(result)

    def cancel_paper_order(self, owner: str, order_id: str) -> dict:
        with self.connect() as db:
            cursor = db.execute("UPDATE paper_orders SET status='cancelled' WHERE id=? AND owner=? AND status='pending'",
                                (order_id, owner))
            if cursor.rowcount == 0:
                raise LookupError("Pending paper order not found.")
        return {"id": order_id, "status": "cancelled"}

    def set_leaderboard_opt_in(self, owner: str, enabled: bool) -> dict:
        with self.connect() as db:
            db.execute("INSERT INTO paper_preferences VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET "
                       "leaderboard_opt_in=excluded.leaderboard_opt_in", (owner, int(enabled)))
        return {"leaderboard_opt_in": enabled}

    def paper_leaderboard(self, limit: int = 20) -> list:
        with self.connect() as db:
            owners = [row[0] for row in db.execute("SELECT a.owner FROM paper_accounts a "
                "JOIN paper_preferences p ON p.owner=a.owner WHERE p.leaderboard_opt_in=1 "
                "ORDER BY a.updated_at DESC LIMIT ?", (limit,))]
        ranked = []
        for owner in owners:
            account = self.paper_account(owner)
            if account["starting_balance"] > 0:
                ranked.append({"trader": f"Trader {hashlib.sha256(owner.encode()).hexdigest()[:6].upper()}",
                               "equity": account["equity"], "total_pnl": account["total_pnl"],
                               "return_pct": account["return_pct"]})
        return sorted(ranked, key=lambda item: item["return_pct"], reverse=True)

    def create_automation(self, owner: str, payload: dict) -> dict:
        strategy_id = str(payload["strategy_id"])
        interval = int(payload["interval_minutes"])
        quantity = int(payload["quantity"])
        if not 1 <= interval <= 1440:
            raise ValueError("Automation interval must be between 1 and 1,440 minutes.")
        if not 1 <= quantity <= 1_000_000:
            raise ValueError("Automated order quantity must be between 1 and 1,000,000 shares.")
        with self.connect() as db:
            strategy = db.execute("SELECT id FROM analysis_strategies WHERE id=? AND owner=?", (strategy_id, owner)).fetchone()
        if strategy is None:
            raise LookupError("Saved strategy not found.")
        automation = {"id": str(uuid.uuid4()), "strategy_id": strategy_id,
                      "interval_minutes": interval, "quantity": quantity,
                      "auto_trade": bool(payload["auto_trade"]), "enabled": True,
                      "created_at": datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute("INSERT INTO analysis_automations VALUES(?,?,?,?,?,?,1,NULL,NULL,NULL,?)",
                       (automation["id"], owner, strategy_id, interval, quantity,
                        int(automation["auto_trade"]), automation["created_at"]))
        return automation

    def automations(self, owner: str) -> list:
        with self.connect() as db:
            rows = db.execute("SELECT a.*,s.name AS strategy_name,s.symbol FROM analysis_automations a "
                "JOIN analysis_strategies s ON s.id=a.strategy_id WHERE a.owner=? ORDER BY a.created_at DESC",
                (owner,)).fetchall()
        return [{"id": row["id"], "strategy_id": row["strategy_id"], "strategy_name": row["strategy_name"],
                 "symbol": row["symbol"], "interval_minutes": row["interval_minutes"],
                 "quantity": row["quantity"], "auto_trade": bool(row["auto_trade"]),
                 "enabled": bool(row["enabled"]), "last_checked_at": row["last_checked_at"],
                 "last_signal_date": row["last_signal_date"], "created_at": row["created_at"]} for row in rows]

    def set_automation_enabled(self, owner: str, automation_id: str, enabled: bool) -> dict:
        with self.connect() as db:
            cursor = db.execute("UPDATE analysis_automations SET enabled=? WHERE id=? AND owner=?",
                                (int(enabled), automation_id, owner))
            if cursor.rowcount == 0:
                raise LookupError("Automation not found.")
        return {"id": automation_id, "enabled": enabled}

    def delete_automation(self, owner: str, automation_id: str) -> dict:
        with self.connect() as db:
            cursor = db.execute("DELETE FROM analysis_automations WHERE id=? AND owner=?", (automation_id, owner))
            if cursor.rowcount == 0:
                raise LookupError("Automation not found.")
            db.execute("DELETE FROM analysis_alerts WHERE automation_id=? AND owner=?", (automation_id, owner))
        return {"deleted": True, "id": automation_id}

    def alerts(self, owner: str) -> list:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM analysis_alerts WHERE owner=? ORDER BY created_at DESC LIMIT 100",
                              (owner,)).fetchall()
        return [{"id": row["id"], "message": row["message"], "details": json.loads(row["details_json"]),
                 "is_read": bool(row["is_read"]), "created_at": row["created_at"]} for row in rows]

    def mark_alert_read(self, owner: str, alert_id: str) -> dict:
        with self.connect() as db:
            cursor = db.execute("UPDATE analysis_alerts SET is_read=1 WHERE id=? AND owner=?", (alert_id, owner))
            if cursor.rowcount == 0:
                raise LookupError("Alert not found.")
        return {"id": alert_id, "is_read": True}

    @staticmethod
    def _webhook_provider(webhook_url: str) -> str:
        parsed = urlparse(webhook_url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Webhook must be a secure HTTPS Slack or Discord URL.")
        if host == "hooks.slack.com" and parsed.path.startswith("/services/"):
            return "slack"
        if host in {"discord.com", "discordapp.com"} and parsed.path.startswith("/api/webhooks/"):
            return "discord"
        raise ValueError("Only Slack hooks.slack.com and Discord webhook endpoints are supported.")

    def set_alert_webhook(self, owner: str, webhook_url: str) -> dict:
        provider = self._webhook_provider(webhook_url)
        with self.connect() as db:
            db.execute("INSERT INTO analysis_alert_webhooks VALUES(?,?,?,?) ON CONFLICT(owner) DO UPDATE SET "
                       "provider=excluded.provider,webhook_url=excluded.webhook_url,updated_at=excluded.updated_at",
                       (owner, provider, webhook_url, datetime.now(timezone.utc).isoformat()))
        return {"provider": provider, "configured": True}

    def remove_alert_webhook(self, owner: str) -> dict:
        with self.connect() as db:
            db.execute("DELETE FROM analysis_alert_webhooks WHERE owner=?", (owner,))
        return {"configured": False}

    def alert_webhook_status(self, owner: str) -> dict:
        with self.connect() as db:
            row = db.execute("SELECT provider,updated_at FROM analysis_alert_webhooks WHERE owner=?", (owner,)).fetchone()
        return {"configured": bool(row), "provider": row["provider"] if row else None,
                "updated_at": row["updated_at"] if row else None}

    def _deliver_alert_webhook(self, owner: str, message: str):
        with self.connect() as db:
            row = db.execute("SELECT provider,webhook_url FROM analysis_alert_webhooks WHERE owner=?", (owner,)).fetchone()
        if row is None:
            return
        # Revalidate the destination and disable redirects/proxy env to keep delivery scoped.
        provider = self._webhook_provider(row["webhook_url"])
        payload = {"text": message} if provider == "slack" else {"content": message}
        request = Request(row["webhook_url"], data=json_module.dumps(payload).encode(),
                          headers={"Content-Type": "application/json", "User-Agent": "AlgoPredict-Alerts/1.0"}, method="POST")
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        try:
            opener = build_opener(ProxyHandler({}), NoRedirect())
            with opener.open(request, timeout=4) as response:
                if response.status >= 400:
                    raise RuntimeError("Webhook returned an error status.")
        except Exception:
            # The persisted in-app alert remains available if external delivery fails.
            return

    def create_public_api_key(self, owner: str) -> dict:
        with self.connect() as db:
            count = db.execute("SELECT COUNT(*) FROM analysis_public_api_keys WHERE owner=?", (owner,)).fetchone()[0]
            if count >= 3:
                raise ValueError("A workspace can have at most three public API keys.")
            key_id = str(uuid.uuid4())
            secret = "ap_live_" + secrets.token_urlsafe(32)
            created = datetime.now(timezone.utc).isoformat()
            db.execute("INSERT INTO analysis_public_api_keys VALUES(?,?,?,?,NULL)",
                       (key_id, owner, hashlib.sha256(secret.encode()).hexdigest(), created))
        return {"id": key_id, "secret": secret, "created_at": created}

    def public_api_keys(self, owner: str) -> list:
        with self.connect() as db:
            rows = db.execute("SELECT id,created_at,last_used_at FROM analysis_public_api_keys WHERE owner=? "
                              "ORDER BY created_at DESC", (owner,)).fetchall()
        return [dict(row) for row in rows]

    def revoke_public_api_key(self, owner: str, key_id: str) -> dict:
        with self.connect() as db:
            cursor = db.execute("DELETE FROM analysis_public_api_keys WHERE id=? AND owner=?", (key_id, owner))
            if cursor.rowcount == 0:
                raise LookupError("API key not found.")
        return {"id": key_id, "revoked": True}

    def public_api_key_owner(self, secret: str) -> str | None:
        if not secret.startswith("ap_live_") or len(secret) > 128:
            return None
        digest = hashlib.sha256(secret.encode()).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT id,owner FROM analysis_public_api_keys WHERE key_hash=?", (digest,)).fetchone()
            if row is None:
                return None
            db.execute("UPDATE analysis_public_api_keys SET last_used_at=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), row["id"]))
        return row["owner"]

    def automation_tick(self) -> int:
        """Check due schedules against the newest locally cached daily candle."""
        now = datetime.now(timezone.utc)
        with self.connect() as db:
            jobs = db.execute("SELECT * FROM analysis_automations WHERE enabled=1").fetchall()
        created_alerts = 0
        for job in jobs:
            previous_check = datetime.fromisoformat(job["last_checked_at"]) if job["last_checked_at"] else None
            if previous_check and (now - previous_check).total_seconds() < job["interval_minutes"] * 60:
                continue
            with self.connect() as db:
                strategy_row = db.execute("SELECT * FROM analysis_strategies WHERE id=? AND owner=?",
                                          (job["strategy_id"], job["owner"])).fetchone()
            if strategy_row is None:
                continue
            strategy = self._strategy(strategy_row)
            dataset, frame, _, _ = self._dataset(job["owner"], strategy["symbol"])
            latest_date = str(frame["date"].iloc[-1])
            new_date = latest_date > (job["last_signal_date"] or "")
            target = current_target(frame, strategy["strategy_type"], strategy["parameters"]) if new_date else job["last_target"]
            previous_target = job["last_target"]
            changed = new_date and target != previous_target and (previous_target is not None or target == 1)
            order_result = None
            if changed and job["auto_trade"]:
                try:
                    with self.connect() as db:
                        holding = db.execute("SELECT quantity FROM paper_positions WHERE owner=? AND symbol=?",
                                             (job["owner"], strategy["symbol"])).fetchone()
                    if target and (holding is None or holding["quantity"] == 0):
                        order_result = self.place_paper_order(job["owner"], {"symbol": strategy["symbol"], "as_of": latest_date,
                            "side": "BUY", "order_type": "market", "quantity": job["quantity"], "trigger_price": None})
                    elif not target and holding and holding["quantity"] > 0:
                        order_result = self.place_paper_order(job["owner"], {"symbol": strategy["symbol"], "as_of": latest_date,
                            "side": "SELL", "order_type": "market", "quantity": int(holding["quantity"]), "trigger_price": None})
                except ValueError as exc:
                    order_result = {"status": "rejected", "reason": str(exc)}
            if changed:
                action = "BUY signal" if target else "EXIT signal"
                suffix = f" Paper order {order_result['status']}." if order_result else ""
                message = f"{strategy['name']}: {action} for {strategy['symbol']} on {latest_date}.{suffix}"
                details = {"strategy_id": strategy["id"], "symbol": strategy["symbol"],
                           "date": latest_date, "target": target, "order": order_result}
                with self.connect() as db:
                    db.execute("INSERT INTO analysis_alerts VALUES(?,?,?,?,?,0,?)",
                               (str(uuid.uuid4()), job["owner"], job["id"], message,
                                canonical_json(details), now.isoformat()))
                self._deliver_alert_webhook(job["owner"], message)
                created_alerts += 1
            with self.connect() as db:
                db.execute("UPDATE analysis_automations SET last_checked_at=?,last_signal_date=?,last_target=? WHERE id=?",
                           (now.isoformat(), latest_date if new_date else job["last_signal_date"], target, job["id"]))
        return created_alerts


_store = None
_store_lock = threading.Lock()


def get_store() -> AnalysisStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = AnalysisStore(Path(os.environ.get("ANALYSIS_DB_PATH", str(ROOT / "research.sqlite3"))))
    return _store
