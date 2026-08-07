"""Read-only Yahoo Finance provider for Dividend Bot market and fundamental data.

The provider retrieves quotes, price history, dividends, and normalized fundamental
fields used by the Dividend Opportunity Quality components. It never contacts a
broker, places orders, or mutates portfolio state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

MODULE_NAME = "yahoo_finance_provider"
MODULE_VERSION = "1.1.0"
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


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


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
            "volume": _number(fast_info.get("last_volume") or info.get("regularMarketVolume") or info.get("volume")),
            "average_volume": _number(info.get("averageVolume")),
            "average_volume_10d": _number(info.get("averageVolume10days")),
            "dividend_rate": _number(info.get("dividendRate")),
            "dividend_yield": _number(info.get("dividendYield")),
            "trailing_annual_dividend_yield": _number(info.get("trailingAnnualDividendYield")),
            "five_year_avg_dividend_yield": _number(info.get("fiveYearAvgDividendYield")),
            "payout_ratio": _number(info.get("payoutRatio")),
            "trailing_pe": _number(info.get("trailingPE")),
            "forward_pe": _number(info.get("forwardPE")),
            "peg_ratio": _number(info.get("pegRatio")),
            "price_to_book": _number(info.get("priceToBook")),
            "price_to_sales": _number(info.get("priceToSalesTrailing12Months")),
            "enterprise_to_ebitda": _number(info.get("enterpriseToEbitda")),
            "enterprise_to_revenue": _number(info.get("enterpriseToRevenue")),
            "beta": _number(info.get("beta")),
            "beta_3y": _number(info.get("beta3Year")),
            "fifty_two_week_high": _number(info.get("fiftyTwoWeekHigh")),
            "fifty_two_week_low": _number(info.get("fiftyTwoWeekLow")),
            "fifty_day_average": _number(info.get("fiftyDayAverage")),
            "two_hundred_day_average": _number(info.get("twoHundredDayAverage")),
            "return_on_equity": _number(info.get("returnOnEquity")),
            "return_on_assets": _number(info.get("returnOnAssets")),
            "profit_margin": _number(info.get("profitMargins")),
            "operating_margin": _number(info.get("operatingMargins")),
            "gross_margin": _number(info.get("grossMargins")),
            "free_cash_flow": _number(info.get("freeCashflow")),
            "operating_cash_flow": _number(info.get("operatingCashflow")),
            "revenue_growth": _number(info.get("revenueGrowth")),
            "earnings_growth": _number(info.get("earningsGrowth")),
            "earnings_quarterly_growth": _number(info.get("earningsQuarterlyGrowth")),
            "debt_to_equity": _number(info.get("debtToEquity")),
            "current_ratio": _number(info.get("currentRatio")),
            "quick_ratio": _number(info.get("quickRatio")),
            "total_cash": _number(info.get("totalCash")),
            "total_debt": _number(info.get("totalDebt")),
            "total_revenue": _number(info.get("totalRevenue")),
            "ebitda": _number(info.get("ebitda")),
            "total_assets": _number(info.get("totalAssets")),
            "three_year_average_return": _number(info.get("threeYearAverageReturn")),
            "five_year_average_return": _number(info.get("fiveYearAverageReturn")),
            "ytd_return": _number(info.get("ytdReturn")),
            "annual_report_expense_ratio": _number(info.get("annualReportExpenseRatio")),
            "morningstar_risk_rating": _number(info.get("morningStarRiskRating")),
            "sector": _text(info.get("sector")),
            "industry": _text(info.get("industry")),
            "category": _text(info.get("category")),
            "fund_family": _text(info.get("fundFamily")),
            "quote_type": _text(info.get("quoteType")),
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
