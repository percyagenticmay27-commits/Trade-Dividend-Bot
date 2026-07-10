"""Read-only Yahoo Finance provider for Version 1.1 market data.

The provider retrieves quotes, price history, dividends, and basic fundamentals.
All results are normalized to plain dictionaries before entering the bot pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

MODULE_NAME = "yahoo_finance_provider"
MODULE_VERSION = "1.0.0"
PROVIDER_NAME = "YAHOO_FINANCE"
READ_ONLY = True
BROKER_EXECUTION_ENABLED = False


class MarketDataProviderError(RuntimeError):
    pass


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_yfinance():
    try:
        import yfinance as yf  # type: ignore
    except ImportError as exc:
        raise MarketDataProviderError("yfinance is not installed") from exc
    return yf


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class YahooFinanceProvider:
    timeout_seconds: int = 15

    def get_quote(self, symbol: str) -> dict[str, Any]:
        ticker_symbol = symbol.strip().upper()
        if not ticker_symbol:
            raise ValueError("symbol is required")
        yf = _load_yfinance()
        ticker = yf.Ticker(ticker_symbol)
        try:
            fast_info = dict(getattr(ticker, "fast_info", {}) or {})
            info = dict(getattr(ticker, "info", {}) or {})
        except Exception as exc:  # provider boundary
            raise MarketDataProviderError(f"quote retrieval failed for {ticker_symbol}: {exc}") from exc
        price = (
            _number(fast_info.get("last_price"))
            or _number(fast_info.get("lastPrice"))
            or _number(info.get("currentPrice"))
            or _number(info.get("regularMarketPrice"))
        )
        return {
            "provider": PROVIDER_NAME,
            "retrieved_at_utc": _utc_now_text(),
            "symbol": ticker_symbol,
            "price": price,
            "currency": info.get("currency") or fast_info.get("currency"),
            "previous_close": _number(fast_info.get("previous_close") or info.get("previousClose")),
            "market_cap": _number(fast_info.get("market_cap") or info.get("marketCap")),
            "dividend_rate": _number(info.get("dividendRate")),
            "dividend_yield": _number(info.get("dividendYield")),
            "trailing_pe": _number(info.get("trailingPE")),
            "forward_pe": _number(info.get("forwardPE")),
            "beta": _number(info.get("beta")),
            "fifty_two_week_high": _number(info.get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": _number(info.get("fiftyTwoWeekLow")),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "quote_type": info.get("quoteType"),
        }

    def get_history(self, symbol: str, period: str = "1y", interval: str = "1d") -> dict[str, Any]:
        ticker_symbol = symbol.strip().upper()
        if not ticker_symbol:
            raise ValueError("symbol is required")
        yf = _load_yfinance()
        try:
            frame = yf.Ticker(ticker_symbol).history(period=period, interval=interval, auto_adjust=False)
        except Exception as exc:
            raise MarketDataProviderError(f"history retrieval failed for {ticker_symbol}: {exc}") from exc
        rows: list[dict[str, Any]] = []
        if frame is not None and not getattr(frame, "empty", True):
            for index, row in frame.iterrows():
                rows.append({
                    "date": index.isoformat() if hasattr(index, "isoformat") else str(index),
                    "open": _number(row.get("Open")),
                    "high": _number(row.get("High")),
                    "low": _number(row.get("Low")),
                    "close": _number(row.get("Close")),
                    "adj_close": _number(row.get("Adj Close")),
                    "volume": _number(row.get("Volume")),
                    "dividends": _number(row.get("Dividends")) or 0.0,
                    "stock_splits": _number(row.get("Stock Splits")) or 0.0,
                })
        return {
            "provider": PROVIDER_NAME,
            "retrieved_at_utc": _utc_now_text(),
            "symbol": ticker_symbol,
            "period": period,
            "interval": interval,
            "rows": rows,
        }

    def get_dividends(self, symbol: str, period: str = "5y") -> dict[str, Any]:
        history = self.get_history(symbol, period=period, interval="1d")
        payments = [
            {"date": row["date"], "amount": row["dividends"]}
            for row in history["rows"]
            if (row.get("dividends") or 0) > 0
        ]
        return {
            "provider": PROVIDER_NAME,
            "retrieved_at_utc": _utc_now_text(),
            "symbol": history["symbol"],
            "period": period,
            "payments": payments,
        }

    def get_quotes(self, symbols: Iterable[str]) -> list[dict[str, Any]]:
        return [self.get_quote(symbol) for symbol in symbols]
