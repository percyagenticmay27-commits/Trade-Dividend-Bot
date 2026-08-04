"""Stooq fallback source with provider-aware symbols and explicit diagnostics."""
from __future__ import annotations

import csv
import urllib.error
import urllib.parse
import urllib.request
from datetime import timezone
from typing import Any

from src.dividend_bot.provider_symbol_normalizer import normalize_symbol


class StooqDataUnavailable(RuntimeError):
    """Raised when Stooq cannot provide a usable CSV response."""


class ProviderAwareStooqSource:
    """Read-only Stooq daily-data fallback.

    Quote and history requests share the exact same normalized provider
    symbol and download endpoint.  This prevents quote/history symbol drift.
    """

    name = "STOOQ"
    base_url = "https://stooq.com/q/d/l/"

    def _download_url(self, symbol: str) -> tuple[str, str]:
        normalized = normalize_symbol(symbol, self.name)
        query = urllib.parse.urlencode({"s": normalized.provider_symbol, "i": "d"})
        return normalized.provider_symbol, f"{self.base_url}?{query}"

    def _history(self, symbol: str) -> list[dict[str, Any]]:
        provider_symbol, url = self._download_url(symbol)
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TradeDividendBot-EnterpriseMarketData/1.0",
                "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.1",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status = getattr(response, "status", 200)
                content_type = (response.headers.get("Content-Type") or "").lower()
                text = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise StooqDataUnavailable(
                    f"STOOQ_DOWNLOAD_ENDPOINT_HTTP_404 symbol={provider_symbol}"
                ) from exc
            if exc.code == 429:
                raise StooqDataUnavailable("STOOQ_RATE_LIMITED") from exc
            raise StooqDataUnavailable(f"STOOQ_HTTP_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise StooqDataUnavailable(f"STOOQ_UPSTREAM_UNAVAILABLE: {exc.reason}") from exc

        stripped = text.lstrip()
        if status != 200:
            raise StooqDataUnavailable(f"STOOQ_HTTP_{status}")
        if stripped.startswith("<") or "text/html" in content_type:
            raise StooqDataUnavailable("STOOQ_NON_CSV_RESPONSE")

        rows = list(csv.DictReader(text.splitlines()))
        required = {"Date", "Open", "High", "Low", "Close"}
        if not rows or not required.issubset(rows[0]):
            raise StooqDataUnavailable(
                f"STOOQ_SYMBOL_OR_DOWNLOAD_UNAVAILABLE symbol={provider_symbol}"
            )
        return [
            {
                "date": row["Date"],
                "open": row["Open"],
                "high": row["High"],
                "low": row["Low"],
                "close": row["Close"],
                "adjusted_close": None,
                "volume": row.get("Volume", 0),
            }
            for row in rows
        ]

    def get_quote(self, symbol: str) -> dict[str, Any]:
        bar = self._history(symbol)[-1]
        timestamp = f"{bar['date']}T21:00:00+00:00"
        return {
            "symbol": symbol.strip().upper(),
            "price": float(bar["close"]),
            "quote_timestamp": timestamp,
            "trading_date": bar["date"],
            "provider": self.name,
            "source_type": "LATEST_DAILY_CLOSE",
            "confidence": 0.70,
            "warnings": ["Stooq quote is latest daily close"],
        }

    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        if interval != "1d":
            raise StooqDataUnavailable("Stooq Version 1 supports interval=1d only")
        return {
            "symbol": symbol.strip().upper(),
            "interval": interval,
            "period": period,
            "provider": self.name,
            "generated_at": __import__("datetime").datetime.now(timezone.utc).isoformat(),
            "corporate_action_adjusted": False,
            "split_history": [],
            "dividend_history": [],
            "bars": self._history(symbol),
            "warnings": [
                "Adjusted close and corporate actions unavailable from Stooq fallback"
            ],
        }
