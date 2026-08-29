"""
data_prep.py

PURPOSE:
  Downloads RELIANCE.NS daily data via yfinance (using Ticker.history which
  is more reliable than yf.download in newer yfinance versions), engineers
  technical features, and saves to data/reliance_features.csv.

HOW TO RUN (from project root):
  .\\venv\\Scripts\\python src\\data_prep.py
"""

import os
import sys
import pandas as pd
import numpy as np

# ── Attempt yfinance import ───────────────────────────────────────────────────
try:
    import yfinance as yf
except ImportError:
    print("ERROR: yfinance not installed. Run: pip install yfinance")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
def compute_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    """
    Computes the RSI (Relative Strength Index) manually.
    Uses Wilder's smoothing (EWM with alpha = 1/length).
    RSI = 100 - 100/(1 + RS)   where RS = avg_gain / avg_loss
    """
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


# ─────────────────────────────────────────────────────────────────────────────
def download_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    Downloads OHLCV data.  Tries Ticker.history() first (more reliable in
    yfinance ≥ 0.2.x), then falls back to yf.download() if that fails.
    """
    print(f"  Trying Ticker('{ticker}').history() ...")
    try:
        t  = yf.Ticker(ticker)
        df = t.history(start=start, end=end, auto_adjust=True)
        if df is not None and not df.empty:
            # history() returns columns like Open, High, Low, Close, Volume, Dividends, Stock Splits
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.index = df.index.tz_localize(None)   # drop timezone so date comparisons work cleanly
            print(f"  Ticker.history() succeeded -> {len(df)} rows")
            return df
    except Exception as e:
        print(f"  Ticker.history() failed: {e}")

    print(f"  Falling back to yf.download() ...")
    try:
        df = yf.download(ticker, start=start, end=end,
                         auto_adjust=True, progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            print(f"  yf.download() succeeded -> {len(df)} rows")
            return df
    except Exception as e:
        print(f"  yf.download() also failed: {e}")

    return pd.DataFrame()


# ─────────────────────────────────────────────────────────────────────────────
def prepare_data():
    ticker     = "RELIANCE.NS"
    start_date = "2020-01-01"
    end_date   = "2026-02-01"

    script_dir  = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_dir  = os.path.join(project_dir, "data")
    output_file = os.path.join(output_dir, "reliance_features.csv")
    os.makedirs(output_dir, exist_ok=True)

    # -- 1. Download -----------------------------------------------------------
    print(f"[1/5] Downloading {ticker} ({start_date} to {end_date}) ...")
    df = download_data(ticker, start_date, end_date)

    if df.empty:
        print("\n" + "="*60)
        print("ERROR: Could not download data.")
        print("Possible causes:")
        print("  • No internet / firewall blocking finance.yahoo.com")
        print("  • Yahoo Finance blocking your IP (try a VPN)")
        print("  • yfinance version mismatch")
        print("\nQuick test — open a browser and try:")
        print("  https://finance.yahoo.com/quote/RELIANCE.NS/history/")
        print("="*60)
        sys.exit(1)

    print(f"    Raw data shape : {df.shape}")
    print(f"    Columns        : {list(df.columns)}")
    print(f"    Date range     : {df.index[0].date()} -> {df.index[-1].date()}")

    # ── 2. Feature Engineering ────────────────────────────────────────────────
    print("[2/5] Engineering features ...")

    # Price returns over 1, 2, 5 trading days
    df['return_1d'] = df['Close'].pct_change(1)
    df['return_2d'] = df['Close'].pct_change(2)
    df['return_5d'] = df['Close'].pct_change(5)

    # Rolling moving averages
    df['ma5']  = df['Close'].rolling(5).mean()
    df['ma10'] = df['Close'].rolling(10).mean()
    df['ma20'] = df['Close'].rolling(20).mean()
    df['ma50'] = df['Close'].rolling(50).mean()

    # RSI (14-day, manual Wilder's formula)
    df['rsi'] = compute_rsi(df['Close'], length=14)

    # MACD and Signal line (12/26 EMA difference, 9-period EMA signal)
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['macd']        = ema12 - ema26
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()

    # Rolling 10-day volatility of 1-day returns
    df['volatility']    = df['return_1d'].rolling(10).std()

    # Volume percentage change day-over-day
    df['volume_change'] = df['Volume'].pct_change(1)

    # -- 5. Target Variable -------------------------------------------------------
    # NEW TARGET: next-day % return instead of raw price.
    # Rationale: raw closing price is ~a random walk, so predicting it mostly
    # rewards reproducing today's price (naive baseline wins). Predicting the
    # RETURN isolates actual signal. The 'Close' column is kept in the CSV so
    # training scripts can reconstruct the INR price after predicting the return.
    #   target = (tomorrow_close - today_close) / today_close
    df['target'] = (df['Close'].shift(-1) - df['Close']) / df['Close']

    # -- 4. Drop NaN / Inf Rows ----------------------------------------------------
    # pct_change() on a 0-volume day produces inf; replace before dropping NaNs
    print("[3/5] Replacing inf values and dropping NaN rows ...")
    n_before = len(df)
    df.replace([float('inf'), float('-inf')], float('nan'), inplace=True)
    df.dropna(inplace=True)
    print(f"    {n_before - len(df)} rows dropped -> {len(df)} clean rows remain")

    # ── 5. Save ───────────────────────────────────────────────────────────────
    print(f"[4/5] Saving to {output_file} ...")
    df.to_csv(output_file)

    print(f"[5/5] Done!  Final shape: {df.shape}")
    print(f"      Columns : {list(df.columns)}")
    print(f"      Dates   : {df.index[0].date()} -> {df.index[-1].date()}")


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    prepare_data()
