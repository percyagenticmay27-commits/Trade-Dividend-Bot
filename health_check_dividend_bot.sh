#!/bin/bash
set -e

BOT_DIR="/root/agentic_etf_backtest_snapshots/iteration_20260622_134517"
LOG_FILE="$BOT_DIR/dividend_bot.log"
REPORT_FILE="$BOT_DIR/dividend_bot_health.txt"

{
  echo "Dividend Bot Health Check"
  echo "Generated: $(date)"
  echo ""

  echo "Cron:"
  crontab -l || true
  echo ""

  echo "Recent Log:"
  if [ -f "$LOG_FILE" ]; then
    tail -50 "$LOG_FILE"
  else
    echo "Missing dividend_bot.log"
  fi
  echo ""

  echo "Required Files:"
  for file in run_dividend_bot.sh send_daily_reports.py daily_paper_report.md weekly_portfolio_review.md strategy_health_report.md live_readiness_report.md; do
    if [ -f "$BOT_DIR/$file" ]; then
      echo "OK: $file"
    else
      echo "MISSING: $file"
    fi
  done
} > "$REPORT_FILE"

cat "$REPORT_FILE"
