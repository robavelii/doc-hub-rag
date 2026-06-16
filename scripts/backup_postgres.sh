#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

: "${DATABASE_SYNC_URL:?Set DATABASE_SYNC_URL}"

pg_dump "$DATABASE_SYNC_URL" -Fc -f "$BACKUP_DIR/ragdb_${TIMESTAMP}.dump"
echo "Backup written to $BACKUP_DIR/ragdb_${TIMESTAMP}.dump"
