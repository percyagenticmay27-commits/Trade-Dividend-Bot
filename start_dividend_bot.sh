#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
export DIVIDEND_BOT_ENV="${DIVIDEND_BOT_ENV:-paper}"

# Run the authoritative PAPER ONLY Dividend cycle first. Rebuild realized
# performance directly from the paper ledger before dashboard publication so
# Enterprise P/L cannot consume a stale performance artifact. Dashboard
# publication remains reporting-only and never drives trading or allocation.
python3 run_daily_paper_cycle.py
python3 refresh_dividend_paper_trade_performance.py
python3 refresh_enterprise_dashboards.py
