"""Read-only Robinhood Agent market-data fallback for the Dividend Bot.

The provider wraps the connected MCP operation supplied by the Agentic runtime.
It has no HTTP endpoint, credentials, order methods, or account mutation access.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Mapping

from yahoo_finance_provider import MarketDataProviderError

MODULE_NAME = "robinhood_agent_provider"
MODULE_VERSION = "1.0.0"
PROVIDER_NAME = "ROBINHOOD_AGENT_READ_ONLY"
PLUGIN_APP_ID = "plugin_asdk_app_6a3419ec40fc8191b59c55b9355dc1da"
HISTORICAL_OPERATION = "mcp__codex_apps__robinhood_etf_tradebot_get_equity_historicals"
READ_ONLY = True
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
MAX_SYMBOLS_PER_CALL = 10

ToolInvoker = Callable[[str, Mapping[str, Any]], Mapping[str, Any]]


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _period_start(period: str, end: datetime) -> datetime:
    normalized = period.strip().lower()
    days = {
        "1mo": 40,
        "3mo": 110,
        "6mo": 220,
        "1y": 370,
        "2y": 740,
        "5y": 1850,
        "10y": 3700,
        "max": 7300,
    }.get(normalized)
    if days is None:
        raise MarketDataProviderError(f"unsupported Robinhood history period: {period}")
    return end - timedelta(days=days)


def _number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataProviderError(f"invalid Robinhood {field}: {value!r}") from exc
    if number <= 0 or number != number or number in {float("inf"), float("-inf")}:
        raise MarketDataProviderError(f"invalid Robinhood {field}: {value!r}")
    return number


@dataclass(frozen=True)
class RobinhoodAgentProvider:
    """Historical daily OHLCV adapter around the verified Robinhood MCP tool."""

    invoker: ToolInvoker
    now_factory: Callable[[], datetime] = lambda: datetime.now(timezone.utc)

    def _invoke_history(self, symbol: str, period: str, interval: str) -> Mapping[str, Any]:
        ticker = symbol.strip().upper()
        if not ticker:
            raise ValueError("symbol is required")
        if interval not in {"1d", "day"}:
            raise MarketDataProviderError("Robinhood fallback supports daily history only")
        end = self.now_factory().astimezone(timezone.utc)
        start = _period_start(period, end)
        request = {
            "symbols": [ticker],
            "start_time": _utc_text(start),
            "end_time": _utc_text(end),
            "interval": "day",
            "bounds": "regular",
            "adjustment_type": "split",
        }
        try:
            response = self.invoker(HISTORICAL_OPERATION, request)
        except Exception as exc:  # runtime/tool boundary
            raise MarketDataProviderError(f"Robinhood historical request failed for {ticker}: {exc}") from exc
        if not isinstance(response, Mapping):
            raise MarketDataProviderError("Robinhood response must be a mapping")
        return response

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> dict[str, Any]:
        ticker = symbol.strip().upper()
        response = self._invoke_history(ticker, period, interval)
        data = response.get("data")
        if not isinstance(data, Mapping):
            raise MarketDataProviderError("Robinhood response missing data object")
        not_found = data.get("not_found") or []
        if ticker in {str(value).upper() for value in not_found}:
            raise MarketDataProviderError(f"Robinhood symbol not found: {ticker}")
        results = data.get("results")
        if not isinstance(results, list):
            raise MarketDataProviderError("Robinhood response missing results list")
        result = next(
            (row for row in results if isinstance(row, Mapping) and str(row.get("symbol", "")).upper() == ticker),
            None,
        )
        if result is None:
            raise MarketDataProviderError(f"Robinhood response missing result for {ticker}")
        raw_bars = result.get("bars")
        if not isinstance(raw_bars, list):
            raise MarketDataProviderError(f"Robinhood response missing bars for {ticker}")

        rows: list[dict[str, Any]] = []
        seen_dates: set[str] = set()
        today = self.now_factory().astimezone(timezone.utc).date().isoformat()
        for bar in raw_bars:
            if not isinstance(bar, Mapping) or bar.get("interpolated") is True:
                continue
            begins_at = str(bar.get("begins_at", ""))
            date_text = begins_at[:10]
            if len(date_text) != 10 or date_text >= today:
                continue
            open_price = _number(bar.get("open_price"), "open_price")
            high_price = _number(bar.get("high_price"), "high_price")
            low_price = _number(bar.get("low_price"), "low_price")
            close_price = _number(bar.get("close_price"), "close_price")
            if high_price < max(open_price, low_price, close_price):
                raise MarketDataProviderError(f"invalid Robinhood high relationship for {ticker} on {date_text}")
            if low_price > min(open_price, high_price, close_price):
                raise MarketDataProviderError(f"invalid Robinhood low relationship for {ticker} on {date_text}")
            try:
                volume = int(bar.get("volume"))
            except (TypeError, ValueError) as exc:
                raise MarketDataProviderError(f"invalid Robinhood volume for {ticker} on {date_text}") from exc
            if volume < 0:
                raise MarketDataProviderError(f"invalid Robinhood volume for {ticker} on {date_text}")
            if date_text in seen_dates:
                raise MarketDataProviderError(f"duplicate Robinhood date for {ticker}: {date_text}")
            seen_dates.add(date_text)
            rows.append({
                "date": date_text,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "adj_close": close_price,
                "volume": volume,
                "dividends": 0.0,
                "stock_splits": 0.0,
                "session": str(bar.get("session", "reg")),
                "interpolated": False,
            })
        rows.sort(key=lambda row: row["date"])
        if not rows:
            raise MarketDataProviderError(f"Robinhood returned no completed daily bars for {ticker}")
        return {
            "provider": PROVIDER_NAME,
            "plugin_app_id": PLUGIN_APP_ID,
            "operation": HISTORICAL_OPERATION,
            "retrieved_at_utc": _utc_text(self.now_factory()),
            "symbol": ticker,
            "period": period,
            "interval": "1d",
            "bounds": "regular",
            "adjustment_type": "split",
            "adjusted_close_source": "UNAVAILABLE_USE_CLOSE",
            "corporate_action_adjusted": False,
            "rows": rows,
        }

    def get_quote(self, symbol: str) -> dict[str, Any]:
        history = self.get_history(symbol, period="1y", interval="1d")
        rows = history["rows"]
        latest = rows[-1]
        previous = rows[-2] if len(rows) > 1 else latest
        return {
            "provider": PROVIDER_NAME,
            "retrieved_at_utc": history["retrieved_at_utc"],
            "symbol": history["symbol"],
            "price": latest["close"],
            "previous_close": previous["close"],
            "volume": latest["volume"],
            "adjusted_close_source": "UNAVAILABLE_USE_CLOSE",
            "corporate_action_adjusted": False,
        }

    def get_dividends(self, symbol: str, period: str = "5y") -> dict[str, Any]:
        raise MarketDataProviderError(
            "Robinhood historical OHLCV fallback does not provide dividend-event history"
        )
