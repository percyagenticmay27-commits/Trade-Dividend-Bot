#!/bin/bash
set -e

BOT_DIR="/root/agentic_etf_backtest_snapshots/iteration_20260622_134517"

echo "Creating backup before update..."
"$BOT_DIR/backup_dividend_bot.sh"

echo "Running health check before update..."
"$BOT_DIR/health_check_dividend_bot.sh"

echo "Update placeholder complete."
echo "Copy new files into $BOT_DIR manually, then run:"
echo "./run_dividend_bot.sh"
