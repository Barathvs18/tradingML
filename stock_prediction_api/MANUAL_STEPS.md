# Manual Steps Checklist (Phase 5)

This checklist outlines the strictly manual steps you must perform to integrate your custom historical CSV data and pretrained machine learning models. **These steps cannot be automated because they require your proprietary data and models.**

## 1. Prepare Your Historical Data (`data/`)
- [ ] Create a `data/` directory at the root of the project (if it doesn't exist).
- [ ] Place your CSV files in the `data/` directory.
- [ ] Ensure one CSV file per stock, named precisely by the symbol (e.g., `RELIANCE.csv`).
- [ ] Open `scripts/load_candles.py` and verify that the `COLUMN_MAP` dictionary matches your exact CSV column names.
- [ ] Confirm your CSV timestamps are either in UTC or IST. If they are in a different timezone, update the timezone localization logic in `scripts/load_candles.py`.
- [ ] Run `python -m scripts.load_candles --dir data/ --verify` to validate your data without inserting it into the database. Check the diagnostic output for gaps or duplicates.

## 2. Prepare Your Pretrained Models (`models/`)
- [ ] Create a `models/` directory at the root of the project (if it doesn't exist).
- [ ] Copy all your model files (`.pkl`, `.joblib`, `.h5`, `.pt`) into this directory.
- [ ] If your models require a pre-fitted scaler (e.g., `MinMaxScaler`), copy the scaler pickle file into `models/` as well.
- [ ] **SECURITY WARNING:** Only load pickle files (`.pkl`) that you created yourself. The `pickle` module can execute arbitrary code upon loading.

## 3. Configure the Manifest (`models/manifest.yaml`)
- [ ] Create a `models/manifest.yaml` file.
- [ ] Fill out the YAML entries for each algorithm key you want to override (or add). Use this format:

```yaml
algorithms:
  my_custom_model_key:
    file: "my_xgboost_model.pkl"
    framework: "xgboost"  # options: sklearn, xgboost, tensorflow, torch, python_script
    scaler_file: "my_scaler.pkl" # optional
    lookback_minutes: 60
    features: ["close", "volume", "rsi_14"] # must match the exact feature names extracted in the adapter
    output_type: "signal"
    output_mapping:
      0: "SELL"
      1: "HOLD"
      2: "BUY"
```

## 4. Environment & Dependencies
- [ ] Open `requirements.txt`.
- [ ] Add and pin the exact library versions you used to train your models (e.g., `scikit-learn==1.3.0`, `xgboost==2.0.0`, `tensorflow==2.13.0`, `torch==2.0.1`).
- [ ] Ensure that `data/` and `models/` are added to your `.gitignore` file so large binary files aren't committed to your repository.

## 5. Verification
- [ ] Run the setup checker script to verify everything is in place:
```bash
python -m scripts.check_setup
```
- [ ] Restart your API. The API will attempt to load all models in the manifest and run a dummy prediction on startup. If it fails, check the logs carefully for dimension mismatches or missing features.
