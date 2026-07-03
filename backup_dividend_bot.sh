#!/bin/bash
set -e

BOT_DIR="/root/agentic_etf_backtest_snapshots/iteration_20260622_134517"
BACKUP_DIR="/root/agentic_etf_backups"

mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/dividend_bot_backup_$TIMESTAMP.tar.gz"

tar -czf "$BACKUP_FILE" -C "$(dirname "$BOT_DIR")" "$(basename "$BOT_DIR")"

find "$BACKUP_DIR" -type f -name "dividend_bot_backup_*.tar.gz" -mtime +30 -delete

echo "Backup created: $BACKUP_FILE"
