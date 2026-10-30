"""Re-evaluate saved daily models on their original chronological holdouts."""

import json
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from app.analysis.model import DIRECTIONS, direction, predict, train
from app.analysis.store import ROOT, get_store


def evaluate() -> dict:
    store = get_store()
    results = []
    for stock in store.stocks("shared"):
        _, frame, model, matrix = store._dataset("shared", stock["symbol"])
        report = model["report"]
        returns = frame["close"].shift(-1) / frame["close"] - 1
        indices = frame.index[(frame["date"] >= report["test_start"])
                              & (frame["date"] <= report["test_end"])
                              & matrix.notna().all(axis=1) & returns.notna()]
        # Exercise the same exported JSON inference function as the app, rather
        # than trusting the accuracy saved at training time.
        outputs = [predict(model, matrix.loc[index]) for index in indices]
        estimated = [output["direction"] for output in outputs]
        actual = [direction(float(returns.loc[index]), model["threshold"]) for index in indices]
        baseline = [report["baseline_class"]] * len(actual)
        accuracy = float(accuracy_score(actual, estimated))
        baseline_accuracy = float(accuracy_score(actual, baseline))
        fresh = train(frame)
        training_reproduces_saved_parameters = all(
            np.allclose(model[key], fresh[key], rtol=0, atol=1e-10)
            for key in ["mean", "scale", "coefficients", "intercepts"]
        )
        if abs(accuracy - report["accuracy"]) > 1e-10:
            raise AssertionError(f"{stock['symbol']}: app inference disagrees with its saved evaluation")
        results.append({
            "symbol": stock["symbol"], "name": stock["name"], "model_version": model["version"],
            "test_start": report["test_start"], "test_end": report["test_end"],
            "last_outcome_date": str(frame.loc[indices[-1] + 1, "date"]),
            "training_samples": report["training_samples"], "test_samples": len(actual),
            "correct_predictions": sum(left == right for left, right in zip(actual, estimated)),
            "baseline_correct": sum(left == right for left, right in zip(actual, baseline)),
            "accuracy": accuracy, "baseline_accuracy": baseline_accuracy,
            "difference_percentage_points": (accuracy - baseline_accuracy) * 100,
            "macro_f1": float(f1_score(actual, estimated, labels=DIRECTIONS, average="macro", zero_division=0)),
            "confusion_matrix": confusion_matrix(actual, estimated, labels=DIRECTIONS).tolist(),
            "classes": DIRECTIONS, "baseline_class": report["baseline_class"],
            "probabilities_sum_to_one": all(abs(sum(output["probabilities"].values()) - 1) < 1e-12 for output in outputs),
            "training_reproduces_saved_parameters": training_reproduces_saved_parameters,
            "source": stock["source"],
        })
    samples = sum(row["test_samples"] for row in results)
    if not samples:
        raise RuntimeError("No trained stock models found. Start the local app to import the bundled CSVs first.")
    correct = sum(row["correct_predictions"] for row in results)
    baseline_correct = sum(row["baseline_correct"] for row in results)
    return {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "method": "Saved-model inference on original later-date holdouts; approximately 70/30 chronological split with one boundary sample omitted",
        "forecast": "Next trading session close-to-close direction",
        "threshold_pct": 0.5,
        "stocks": results,
        "combined": {"test_samples": samples, "correct_predictions": correct, "accuracy": correct / samples,
                     "baseline_accuracy": baseline_correct / samples,
                     "difference_percentage_points": (correct - baseline_correct) / samples * 100},
        "limitations": ["Re-evaluates the existing holdout; this is not a new independent dataset.",
                        "Dataset ends April 2021 and can contain unadjusted corporate-action price jumps.",
                        "Direction accuracy does not measure profitability, execution costs or live performance."],
    }


if __name__ == "__main__":
    result = evaluate()
    directory = ROOT / "reports"
    directory.mkdir(exist_ok=True)
    (directory / "model_evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    lines = ["# Daily Indian-stock model evaluation", "", f"Evaluated: {result['evaluated_at']}", "",
             "Saved app models were rerun on later dates excluded from training. A fresh training run was also compared with the saved parameters.", "",
             "| Stock | Correct / tested | Accuracy | Baseline | Difference | Test input dates |",
             "| --- | --- | --- | --- | --- | --- |"]
    for row in result["stocks"]:
        lines.append(f"| {row['symbol']} | {row['correct_predictions']} / {row['test_samples']} | {row['accuracy']:.2%} | {row['baseline_accuracy']:.2%} | {row['difference_percentage_points']:+.2f} pp | {row['test_start']} to {row['test_end']} |")
    total = result["combined"]
    lines.extend(["", f"Combined: **{total['accuracy']:.2%}** ({total['correct_predictions']} correct out of {total['test_samples']} stock-session cases). Baseline: **{total['baseline_accuracy']:.2%}**. Difference: **{total['difference_percentage_points']:+.2f} percentage points**.", "",
                  "The baseline always predicts each stock's most frequent training class. Classification uses UP above +0.5%, DOWN below -0.5%, SIDEWAYS between these thresholds.", "", "## Checks", ""])
    for row in result["stocks"]:
        lines.append(f"- {row['symbol']}: saved accuracy matches rerun inference; training reproduction: {row['training_reproduces_saved_parameters']}; probabilities sum to one: {row['probabilities_sum_to_one']}.")
    lines.extend(["", "## Limits", "", *[f"- {limit}" for limit in result["limitations"]]])
    (directory / "model_evaluation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"stocks": result["stocks"], "combined": total}, indent=2))
