#!/usr/bin/env python3
"""Production refresh entry point using the provider-aware Stooq source."""
from __future__ import annotations

import refresh_enterprise_market_data as refresh
from src.dividend_bot.stooq_market_data_source import ProviderAwareStooqSource


# Keep the established refresh orchestration and contracts unchanged while
# replacing only the Stooq transport implementation used by its provider builder.
refresh.StooqSource = ProviderAwareStooqSource


if __name__ == "__main__":
    raise SystemExit(refresh.main())
