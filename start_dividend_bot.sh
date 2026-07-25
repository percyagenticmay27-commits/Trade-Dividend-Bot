#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
export DIVIDEND_BOT_ENV="${DIVIDEND_BOT_ENV:-paper}"
exec python3 run_daily_paper_cycle.py
