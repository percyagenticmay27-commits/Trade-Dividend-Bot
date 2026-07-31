#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
export DIVIDEND_BOT_ENV="${DIVIDEND_BOT_ENV:-paper}"

# Run the authoritative PAPER ONLY Dividend cycle first. Dashboard publication is
# intentionally sequenced afterward so the portal reflects the newest completed
# reporting evidence and never drives trading or allocation behavior.
python3 run_daily_paper_cycle.py
python3 refresh_enterprise_dashboards.py
