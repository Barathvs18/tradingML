"""Run with python -m unittest discover -s analysis_tests -v (no Postgres needed)."""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analysis.model import DIRECTIONS, features, predict, read_daily_csv, train
from app.analysis.routes import analysis_owner, router
from app.analysis.store import ROOT, AnalysisStore, get_store


class AnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = read_daily_csv((ROOT / "data" / "indian_daily" / "RELIANCE.csv").read_bytes()).head(700)
        cls.raw = cls.frame.to_csv(index=False).encode()
        cls.model = train(cls.frame)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.store = AnalysisStore(Path(self.directory.name) / "test.sqlite3")
        self.store.import_csv("RELIANCE", self.raw)
        self.app = FastAPI()
        self.app.include_router(router, prefix="/app")
        self.app.dependency_overrides[get_store] = lambda: self.store
        self.app.dependency_overrides[analysis_owner] = lambda: "user-a"
        self.client = TestClient(self.app)
        self.date = self.store.dates("user-a", "RELIANCE")[1]

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def analyze(self):
        response = self.client.post("/app/analysis/predict", json={"symbol": "RELIANCE", "as_of": self.date})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_features_do_not_read_future_prices(self):
        original = features(self.frame)
        modified = self.frame.copy()
        modified.loc[401:, ["open", "high", "low", "close", "volume"]] *= 4
        pd.testing.assert_frame_equal(original.iloc[:401], features(modified).iloc[:401])

    def test_training_does_not_read_holdout_prices_or_labels(self):
        modified = self.frame.copy()
        start = modified.index[modified["date"] == self.model["report"]["test_start"]][0]
        modified.loc[start:, ["open", "high", "low", "close"]] *= 1.7
        changed = train(modified)
        for key in ["mean", "scale", "coefficients", "intercepts"]:
            np.testing.assert_allclose(self.model[key], changed[key], rtol=0, atol=1e-12)
        self.assertLess(self.model["report"]["training_outcomes_end"], self.model["report"]["test_start"])

    def test_exported_json_inference_is_deterministic_and_finite(self):
        model = json.loads(json.dumps(self.model, allow_nan=False))
        row = features(self.frame).iloc[-2]
        first = predict(model, row)
        self.assertEqual(first, predict(model, row))
        self.assertEqual(set(first["probabilities"]), set(DIRECTIONS))
        self.assertAlmostEqual(sum(first["probabilities"].values()), 1)
        self.assertTrue(all(0 <= value <= 1 for value in first["probabilities"].values()))

    def test_analysis_hides_actual_outcome_and_future_candles(self):
        result = self.analyze()
        self.assertIsNone(result["outcome"])
        self.assertTrue(result["outcome_available"])
        self.assertEqual(pd.Timestamp(result["history"][-1]["time"], unit="s", tz="UTC").strftime("%Y-%m-%d"), self.date)
        self.assertNotIn("predicted_candles", result)
        self.assertNotIn("return_pct", result)

    def test_reveal_matches_the_actual_next_trading_session(self):
        result = self.analyze()
        response = self.client.post(f"/app/analysis/history/{result['id']}/reveal")
        self.assertEqual(response.status_code, 200)
        actual = response.json()["outcome"]
        position = self.frame.index[self.frame["date"] == self.date][0]
        self.assertEqual(actual["date"], self.frame.iloc[position + 1]["date"])
        self.assertEqual(actual["close"], self.frame.iloc[position + 1]["close"])
        self.assertAlmostEqual(actual["return_pct"], (actual["close"] / result["close"] - 1) * 100)
        self.assertEqual(actual["correct"], actual["direction"] == result["direction"])
        self.assertEqual(self.client.get("/app/analysis/history").json()[0]["outcome"], actual)

    def test_latest_date_has_no_fabricated_outcome(self):
        latest = self.store.dates("user-a", "RELIANCE")[0]
        result = self.client.post("/app/analysis/predict", json={"symbol": "RELIANCE", "as_of": latest}).json()
        self.assertFalse(result["outcome_available"])
        revealed = self.client.post(f"/app/analysis/history/{result['id']}/reveal").json()
        self.assertFalse(revealed["available"])
        self.assertIsNone(revealed["outcome"])

    def test_predictions_and_reveals_are_isolated_by_user(self):
        result = self.analyze()
        self.app.dependency_overrides[analysis_owner] = lambda: "user-b"
        self.assertEqual(self.client.get("/app/analysis/history").json(), [])
        self.assertEqual(self.client.post(f"/app/analysis/history/{result['id']}/reveal").status_code, 404)

    def test_imports_are_isolated_by_user(self):
        self.store.import_csv("TCS", self.raw, "user-a")
        self.assertIn("TCS", [item["symbol"] for item in self.store.stocks("user-a")])
        self.assertNotIn("TCS", [item["symbol"] for item in self.store.stocks("user-b")])

    def test_training_dates_cannot_be_analyzed(self):
        response = self.client.post("/app/analysis/predict", json={"symbol": "RELIANCE", "as_of": self.model["report"]["training_end"]})
        self.assertEqual(response.status_code, 422)

    def test_unknown_symbol_and_non_trading_date(self):
        self.assertEqual(self.client.get("/app/analysis/stocks/MISSING/dates").status_code, 404)
        response = self.client.post("/app/analysis/predict", json={"symbol": "RELIANCE", "as_of": "2000-01-02"})
        self.assertEqual(response.status_code, 422)

    def test_csv_import_and_invalid_upload_do_not_break_existing_dataset(self):
        response = self.client.post("/app/analysis/import?symbol=TCS", content=self.raw, headers={"Content-Type": "text/csv"})
        self.assertEqual(response.status_code, 200, response.text)
        version = self.store.stock("user-a", "TCS")["model_version"]
        invalid = self.client.post("/app/analysis/import?symbol=TCS", content=b"date,close\n2020-01-01,100")
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.store.stock("user-a", "TCS")["model_version"], version)
        self.assertEqual(self.client.post("/app/analysis/import?symbol=../TCS", content=self.raw).status_code, 422)

    def test_bad_rows_duplicate_dates_and_intraday_data_are_rejected(self):
        invalid = self.frame.copy()
        invalid.loc[0, "high"] = 1
        with self.assertRaises(ValueError): read_daily_csv(invalid.to_csv(index=False).encode())
        duplicate = pd.concat([self.frame, self.frame.iloc[:1]])
        with self.assertRaises(ValueError): read_daily_csv(duplicate.to_csv(index=False).encode())
        intraday = self.frame.copy()
        intraday["date"] = intraday["date"] + " 09:15:00"
        with self.assertRaises(ValueError): read_daily_csv(intraday.to_csv(index=False).encode())

    def test_history_survives_restart_and_new_model_import(self):
        result = self.analyze()
        self.store.reveal("user-a", result["id"])
        modified = self.frame.copy()
        modified.iloc[-1, modified.columns.get_loc("volume")] += 100
        self.store.import_csv("RELIANCE", modified.to_csv(index=False).encode(), "user-a")
        restarted = AnalysisStore(self.store.path)
        saved = restarted.history("user-a")[0]
        self.assertEqual(saved["model_version"], result["model_version"])
        self.assertEqual(saved["probabilities"], result["probabilities"])
        self.assertEqual(saved["outcome"], self.store.reveal("user-a", result["id"])["outcome"])

    def test_report_baseline_uses_training_majority_and_counts_all_test_cases(self):
        report = self.client.get("/app/analysis/stocks/RELIANCE/performance").json()
        self.assertEqual(sum(sum(row) for row in report["confusion_matrix"]), report["test_samples"])
        self.assertEqual(sum(row["support"] for row in report["per_class"]), report["test_samples"])
        matrix = features(self.frame)
        returns = self.frame["close"].shift(-1) / self.frame["close"] - 1
        from app.analysis.model import direction
        labels = returns[matrix.notna().all(axis=1) & returns.notna()].map(direction)
        expected = labels.iloc[:report["training_samples"]].value_counts().idxmax()
        self.assertEqual(report["baseline_class"], expected)

    def test_online_backup_restores_predictions_and_reveals(self):
        result = self.analyze()
        self.store.reveal("user-a", result["id"])
        target = Path(self.directory.name) / "backup.sqlite3"
        self.store.backup(target)
        restored = AnalysisStore(target)
        self.assertEqual(restored.history("user-a"), self.store.history("user-a"))
        with restored.connect() as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def test_duplicate_normalized_csv_columns_are_rejected(self):
        duplicate = self.raw.replace(b"date,open,high,low,close,volume", b"date,open,high,low,Close,volume,close")
        response = self.client.post("/app/analysis/import?symbol=TCS", content=duplicate)
        self.assertEqual(response.status_code, 422)

    def test_busy_training_returns_retryable_error(self):
        self.store._training_lock.acquire()
        try:
            response = self.client.post("/app/analysis/import?symbol=TCS", content=self.raw)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers["Retry-After"], "5")
            self.assertEqual(self.client.get("/app/analysis/stocks").status_code, 200)
        finally:
            self.store._training_lock.release()


if __name__ == "__main__":
    unittest.main()
