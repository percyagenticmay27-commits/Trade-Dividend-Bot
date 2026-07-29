"""Compatibility adapter for gradual Dividend Bot market-data migration."""

from __future__ import annotations

from typing import Any

from .orchestrator import MarketDataOrchestrator


class DividendBotMarketDataAdapter:
    """Expose simple legacy-friendly values without leaking provider details."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(self, orchestrator: MarketDataOrchestrator) -> None:
        self._orchestrator = orchestrator

    def get_price_history(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        start: str | None = None,
        end: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        result = self._orchestrator.get_history(
            symbol,
            interval=interval,
            start=start,
            end=end,
            limit=limit,
        )
        return [
            {
                "symbol": bar.symbol,
                "timestamp": bar.timestamp,
                "open": bar.open,
                "high": bar.high,
                "low": bar.low,
                "close": bar.close,
                "volume": bar.volume,
            }
            for bar in result.response.bars
        ]

    def get_latest_price(self, symbol: str, *, interval: str = "1d") -> float:
        rows = self.get_price_history(symbol, interval=interval, limit=1)
        if not rows:
            raise LookupError(f"no market price available for {symbol.strip().upper()}")
        return float(rows[-1]["close"])

    def get_close_series(
        self,
        symbol: str,
        *,
        interval: str = "1d",
        limit: int | None = None,
    ) -> list[float]:
        return [
            float(row["close"])
            for row in self.get_price_history(symbol, interval=interval, limit=limit)
        ]
