#!/usr/bin/env bash
set -euo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
ENV_FILE="${ENV_FILE:-.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-algopredict}"
set -a
source "$ENV_FILE"
set +a
compose=(docker compose --env-file "$ENV_FILE" -p "$COMPOSE_PROJECT_NAME" -f docker-compose.prod.yml)
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -p "$BACKUP_DIR"
stage="$(mktemp -d "$BACKUP_DIR/.incomplete-$stamp-XXXX")"
remote="/app/storage/backup-$stamp.sqlite3"
MONGODB_URL="${MONGODB_URL:?Set MONGODB_URL in ENV_FILE}"

# Install MongoDB Database Tools on the backup host. Keep partial attempts separate.
mongodump --uri "$MONGODB_URL" --archive="$stage/mongodb.archive.gz" --gzip
"${compose[@]}" exec -T api python -m scripts.backup_research "$remote"
"${compose[@]}" cp "api:$remote" "$stage/research.sqlite3"
"${compose[@]}" exec -T api python -c 'from pathlib import Path; import sys; Path(sys.argv[1]).unlink()' "$remote"
test -s "$stage/mongodb.archive.gz"
test -s "$stage/research.sqlite3"
mv "$stage" "$BACKUP_DIR/$stamp"
printf 'Backup saved to %s\n' "$BACKUP_DIR/$stamp"
# Apply retention in your backup service after copying these snapshots off-host.
