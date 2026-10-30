# Daily Indian-stock model evaluation

Evaluated: 2026-10-06T09:40:50.115163+00:00

Saved app models were rerun on later dates excluded from training. A fresh training run was also compared with the saved parameters.

| Stock | Correct / tested | Accuracy | Baseline | Difference | Test input dates |
| --- | --- | --- | --- | --- | --- |
| INFY | 599 / 1586 | 37.77% | 36.38% | +1.39 pp | 2014-12-02 to 2021-04-29 |
| RELIANCE | 581 / 1586 | 36.63% | 38.15% | -1.51 pp | 2014-12-02 to 2021-04-29 |
| TCS | 463 / 1236 | 37.46% | 36.00% | +1.46 pp | 2016-05-04 to 2021-04-29 |

Combined: **37.27%** (1643 correct out of 4408 stock-session cases). Baseline: **36.91%**. Difference: **+0.36 percentage points**.

The baseline always predicts each stock's most frequent training class. Classification uses UP above +0.5%, DOWN below -0.5%, SIDEWAYS between these thresholds.

## Checks

- INFY: saved accuracy matches rerun inference; training reproduction: True; probabilities sum to one: True.
- RELIANCE: saved accuracy matches rerun inference; training reproduction: True; probabilities sum to one: True.
- TCS: saved accuracy matches rerun inference; training reproduction: True; probabilities sum to one: True.

## Limits

- Re-evaluates the existing holdout; this is not a new independent dataset.
- Dataset ends April 2021 and can contain unadjusted corporate-action price jumps.
- Direction accuracy does not measure profitability, execution costs or live performance.
