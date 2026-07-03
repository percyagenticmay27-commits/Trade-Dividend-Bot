#!/bin/bash
set -e

BOT_DIR="/root/agentic_etf_backtest_snapshots/iteration_20260622_134517"
LOG_FILE="$BOT_DIR/dividend_bot.log"
ARCHIVE_DIR="$BOT_DIR/log_archive"

mkdir -p "$ARCHIVE_DIR"

if [ -f "$LOG_FILE" ]; then
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  cp "$LOG_FILE" "$ARCHIVE_DIR/dividend_bot_$TIMESTAMP.log"
  : > "$LOG_FILE"
fi

find "$ARCHIVE_DIR" -type f -name "*.log" -mtime +30 -delete

echo "Log rotation complete."
