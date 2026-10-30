"""Create a consistent online snapshot of the research SQLite database."""
import argparse
from pathlib import Path

from app.analysis.store import get_store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    args = parser.parse_args()
    store = get_store()
    if args.target.resolve() == store.path.resolve():
        parser.error("Backup target must differ from the source database.")
    if args.target.exists():
        parser.error("Backup target already exists; choose a new path.")
    store.backup(args.target)
    print(f"Research backup created: {args.target.name}")


if __name__ == "__main__":
    main()
