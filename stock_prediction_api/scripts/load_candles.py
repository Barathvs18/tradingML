import argparse
import asyncio
import pandas as pd
from pathlib import Path
import time
import sys
import os

# Add the parent directory to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.db.mongo import connect_mongo, close_mongo, get_database

# ==========================================
# CONFIGURABLE COLUMN MAPPING
# Change these values to match your CSV headers
# ==========================================
COLUMN_MAPPING = {
    "datetime": "date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "volume": "volume"
}
TIMEZONE = 'America/New_York' # Timezone of the supplied SPY intraday data

CHUNK_SIZE = 50000
INSERT_BATCH_SIZE = 4000

async def verify_stock(filepath: Path):
    symbol = filepath.stem
    print(f"--- Verifying {symbol} ---")
    
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return
        
    rename_map = {v: k for k, v in COLUMN_MAPPING.items()}
    df = df.rename(columns=rename_map)
    
    required = ['datetime', 'open', 'high', 'low', 'close', 'volume']
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"❌ Missing mapped columns: {missing}")
        return
        
    initial_len = len(df)
    
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime')
    
    duplicates = df.duplicated(subset=['datetime']).sum()
    
    # Calculate missing minutes (naive gap detection)
    df = df.set_index('datetime')
    # Resample to 1 minute and count NaNs
    resampled = df.resample('1min').asfreq()
    missing_minutes = resampled['close'].isna().sum()
    
    date_min = df.index.min()
    date_max = df.index.max()
    
    print(f"✅ Row Count: {initial_len}")
    print(f"✅ Date Range: {date_min} to {date_max}")
    print(f"⚠️ Missing Minute Gaps: {missing_minutes}")
    print(f"⚠️ Duplicates: {duplicates}")
    print("----------------------------\n")


async def load_stock(filepath: Path):
    symbol = filepath.stem
    print(f"Processing {symbol}...")
    
    rename_map = {v: k for k, v in COLUMN_MAPPING.items()}
    database = get_database()
    await database.stocks.update_one({"symbol": symbol}, {"$setOnInsert": {
        "symbol": symbol, "name": symbol, "exchange": "NYSE"}}, upsert=True)
            
    loaded = 0
    skipped = 0
    date_min = None
    date_max = None
    try:
        chunks = pd.read_csv(filepath, chunksize=CHUNK_SIZE)
        for df in chunks:
            df = df.rename(columns=rename_map)
            required = ['datetime', 'open', 'high', 'low', 'close', 'volume']
            missing = [column for column in required if column not in df.columns]
            if missing:
                raise ValueError(f"Missing mapped columns: {missing}")
            initial_len = len(df)
            for column in ['open', 'high', 'low', 'close', 'volume']:
                df[column] = pd.to_numeric(df[column], errors='coerce')
            df['datetime'] = pd.to_datetime(df['datetime'], errors='coerce')
            df = df.dropna(subset=required)
            df = df.drop_duplicates(subset=['datetime'], keep='first')
            df = df[(df['high'] >= df['low']) & (df['open'] > 0) & (df['high'] > 0) & (df['low'] > 0) & (df['close'] > 0)]
            skipped += initial_len - len(df)
            if df.empty:
                continue
            df['datetime'] = df['datetime'].dt.tz_localize(TIMEZONE).dt.tz_convert('UTC')
            date_min = df['datetime'].min() if date_min is None else min(date_min, df['datetime'].min())
            date_max = df['datetime'].max() if date_max is None else max(date_max, df['datetime'].max())
            records = df[['datetime', 'open', 'high', 'low', 'close', 'volume']].rename(columns={'datetime': 'ts'}).to_dict('records')
            from pymongo import UpdateOne
            for start in range(0, len(records), INSERT_BATCH_SIZE):
                batch = records[start:start + INSERT_BATCH_SIZE]
                ops = [UpdateOne({"stock_id": symbol, "ts": row["ts"].to_pydatetime()},
                    {"$setOnInsert": {"stock_id": symbol, "ts": row["ts"].to_pydatetime(),
                     "open": float(row["open"]), "high": float(row["high"]), "low": float(row["low"]),
                     "close": float(row["close"]), "volume": int(row["volume"])}}, upsert=True) for row in batch]
                result = await database.candles.bulk_write(ops, ordered=False)
                loaded += result.upserted_count
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return
    print(f"{symbol} -> Loaded: {loaded}, Skipped: {skipped}, Range: {date_min} to {date_max}")

async def main(data_dir: str, verify_only: bool):
    p = Path(data_dir)
    if not p.exists() or not p.is_dir():
        print(f"Directory {data_dir} does not exist.")
        return
        
    csv_files = list(p.glob("*.csv"))
    print(f"Found {len(csv_files)} CSV files in {data_dir}")
    
    if verify_only:
        for f in csv_files:
            await verify_stock(f)
        return
        
    await connect_mongo()
    start = time.time()
    for f in csv_files:
        await load_stock(f)
        
    await close_mongo()
    print(f"Finished in {time.time() - start:.2f} seconds.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, help="Directory containing CSV files")
    parser.add_argument("--verify", action="store_true", help="Verify data only, do not insert")
    args = parser.parse_args()
    asyncio.run(main(args.dir, args.verify))
