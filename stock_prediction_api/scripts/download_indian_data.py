"""Download public daily NSE research data without a broker or API key."""

import argparse
import csv
import hashlib
import io
import json
import re
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile, is_zipfile

ROOT = Path(__file__).resolve().parents[1]
DATASET = "https://www.kaggle.com/datasets/rohanrao/nifty50-stock-market-data"
UNIVERSE_FILE = ROOT / "data" / "nifty50_2021.json"


def load_universe(path: Path = UNIVERSE_FILE) -> dict[str, str]:
    """Load a dated, auditable universe; membership must not be mistaken for current constituents."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    stocks = payload.get("stocks")
    if not isinstance(stocks, dict) or len(stocks) != 50:
        raise ValueError(f"{path} must define exactly 50 stock symbols.")
    for symbol, name in stocks.items():
        if not re.fullmatch(r"[A-Z0-9&.-]{1,20}", symbol) or not isinstance(name, str) or not name.strip():
            raise ValueError(f"Invalid stock entry: {symbol!r}")
    return stocks


def download(symbol: str, directory: Path, stocks: dict[str, str]) -> dict:
    if symbol not in stocks:
        raise ValueError(f"{symbol} is not in the selected dated universe.")
    url = f"https://www.kaggle.com/api/v1/datasets/download/rohanrao/nifty50-stock-market-data/{symbol}.csv"
    request = Request(url, headers={"User-Agent": "IndianMarketAnalyzer/1.0"})
    with urlopen(request, timeout=60) as response:
        raw = response.read(8_000_001)
    if len(raw) > 8_000_000:
        raise ValueError("Download exceeded the expected single-stock file size.")
    if is_zipfile(io.BytesIO(raw)):
        with ZipFile(io.BytesIO(raw)) as archive:
            matches = [name for name in archive.namelist() if Path(name).name.upper() == f"{symbol}.CSV"]
            if len(matches) != 1:
                raise ValueError(f"Archive does not contain exactly one {symbol}.csv")
            if archive.getinfo(matches[0]).file_size > 8_000_000:
                raise ValueError("Uncompressed CSV is unexpectedly large.")
            raw = archive.read(matches[0])
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    required = {"Date", "Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("The provider did not return the expected OHLCV CSV.")
    rows = [{"date": row["Date"], "open": row["Open"], "high": row["High"],
             "low": row["Low"], "close": row["Close"], "volume": row["Volume"]}
            for row in reader if row.get("Series", "EQ") == "EQ"]
    if len(rows) < 300:
        raise ValueError("Not enough daily records to train and evaluate a model.")
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{symbol}.csv"
    with tempfile.NamedTemporaryFile("w", newline="", encoding="utf-8", dir=directory, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=["date", "open", "high", "low", "close", "volume"])
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(destination)
    print(f"{symbol}: saved {len(rows):,} daily rows ({rows[0]['date']} to {rows[-1]['date']})", flush=True)
    return {"name": stocks[symbol], "source": DATASET, "provider": "Rohan Rao / Kaggle, compiled NSE daily data",
            "interval": "1d", "currency": "INR", "timezone": "Asia/Kolkata", "rows": len(rows),
            "start": rows[0]["date"], "end": rows[-1]["date"], "raw_sha256": hashlib.sha256(raw).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=ROOT / "data" / "indian_daily")
    parser.add_argument("--universe", type=Path, default=UNIVERSE_FILE,
                        help="Dated JSON universe file (default: NIFTY 50 universe used by the Kaggle data).")
    parser.add_argument("--symbols", nargs="+", help="Download selected symbols; defaults to all 50.")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="Exit successfully when one or more provider files cannot be used.")
    args = parser.parse_args()
    stocks = load_universe(args.universe)
    symbols = args.symbols or list(stocks)
    unknown = sorted(set(symbols) - stocks.keys())
    if unknown:
        parser.error(f"symbols not in universe: {', '.join(unknown)}")
    manifest_path = args.dir / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    failures = []
    for symbol in symbols:
        destination = args.dir / f"{symbol}.csv"
        if destination.is_file() and symbol in manifest:
            print(f"{symbol}: already present; skipping (delete the file to refresh)", flush=True)
            continue
        try:
            manifest[symbol] = download(symbol, args.dir, stocks)
            temporary_manifest = manifest_path.with_suffix(".json.tmp")
            temporary_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            temporary_manifest.replace(manifest_path)
        except Exception as exc:
            failures.append((symbol, str(exc)))
            print(f"{symbol}: download failed: {exc}", flush=True)
    if failures:
        if args.allow_incomplete:
            print(f"Completed with {len(failures)} unavailable symbol(s): " +
                  "; ".join(f"{s}: {e}" for s, e in failures), flush=True)
            return
        raise SystemExit(f"{len(failures)} download(s) failed: " + "; ".join(f"{s}: {e}" for s, e in failures))


if __name__ == "__main__":
    main()
