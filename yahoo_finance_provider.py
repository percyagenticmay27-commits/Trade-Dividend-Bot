"""Read-only Yahoo Finance provider for Dividend Bot market and fundamental data.

The provider retrieves quotes, price history, dividends, and normalized fundamental
fields used by the Dividend Opportunity Quality and shared Enterprise Financial Health
components. It never contacts a broker, places orders, or mutates portfolio state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

MODULE_NAME = "yahoo_finance_provider"
MODULE_VERSION = "1.3.0"
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


def _date_text(value: Any) -> str | None:
    """Normalize provider date values without inventing a future date."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc).date().isoformat()
        except (OSError, OverflowError, ValueError):
            return None
    text = _text(value)
    if text is None:
        return None
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return text


def _statement_series(frame: Any, labels: tuple[str, ...]) -> list[float]:
    if frame is None or getattr(frame, "empty", True):
        return []
    index = getattr(frame, "index", [])
    for label in labels:
        if label not in index:
            continue
        try:
            values = list(frame.loc[label])
        except Exception:
            continue
        normalized = [_number(value) for value in values]
        return [value for value in normalized if value is not None]
    return []


def _gross_margin_pair(frame: Any) -> tuple[float | None, float | None]:
    gross_profit = _statement_series(frame, ("Gross Profit", "GrossProfit"))
    total_revenue = _statement_series(frame, ("Total Revenue", "TotalRevenue", "Operating Revenue"))
    if len(gross_profit) < 2 or len(total_revenue) < 2:
        return None, None
    margins: list[float] = []
    for gross, revenue in zip(gross_profit, total_revenue):
        if revenue == 0:
            continue
        margins.append(gross / revenue)
        if len(margins) == 2:
            break
    if len(margins) < 2:
        return None, None
    return margins[0], margins[1]


def _analyst_revision_counts(frame: Any, *, now: datetime) -> tuple[bool, int, int]:
    if frame is None:
        return False, 0, 0
    if getattr(frame, "empty", False):
        return True, 0, 0
    cutoff = now - timedelta(days=90)
    upgrades = 0
    downgrades = 0
    try:
        iterator = frame.iterrows()
    except Exception:
        return False, 0, 0
    for index, row in iterator:
        observed: datetime | None = None
        if isinstance(index, datetime):
            observed = index
        else:
            try:
                observed = datetime.fromisoformat(str(index).replace("Z", "+00:00"))
            except ValueError:
                observed = None
        if observed is not None:
            if observed.tzinfo is None:
                observed = observed.replace(tzinfo=timezone.utc)
            else:
                observed = observed.astimezone(timezone.utc)
            if observed < cutoff:
                continue
        action = str(row.get("Action") or row.get("action") or "").strip().lower()
        if action in {"up", "upgrade"}:
            upgrades += 1
        elif action in {"down", "downgrade"}:
            downgrades += 1
    return True, upgrades, downgrades


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
            "short_name": _text(info.get("shortName")),
            "long_name": _text(info.get("longName")),
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
            "ex_dividend_date": _date_text(info.get("exDividendDate")),
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

    def get_financial_health_inputs(self, symbol: str) -> dict[str, Any]:
        """Return raw, timestamped evidence needed to build all seven shared components."""
        ticker_symbol = symbol.strip().upper()
        if not ticker_symbol:
            raise ValueError("symbol is required")
        yf = _load_yfinance()
        ticker = yf.Ticker(ticker_symbol)
        now = datetime.now(timezone.utc)
        try:
            info = dict(getattr(ticker, "info", {}) or {})
            statements = getattr(ticker, "quarterly_income_stmt", None)
            if statements is None or getattr(statements, "empty", True):
                statements = getattr(ticker, "quarterly_financials", None)
            revisions = getattr(ticker, "upgrades_downgrades", None)
        except Exception as exc:
            raise MarketDataProviderError(
                f"financial-health retrieval failed for {ticker_symbol}: {exc}"
            ) from exc

        gross_margin_current, gross_margin_prior = _gross_margin_pair(statements)
        analyst_available, upgrades, downgrades = _analyst_revision_counts(revisions, now=now)
        return {
            "provider": PROVIDER_NAME,
            "retrieved_at_utc": now.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "symbol": ticker_symbol,
            "sector": _text(info.get("sector")),
            "industry": _text(info.get("industry")),
            "revenue_growth": _number(info.get("revenueGrowth")),
            "eps_growth": _number(info.get("earningsGrowth")) or _number(info.get("earningsQuarterlyGrowth")),
            "operating_cash_flow": _number(info.get("operatingCashflow")),
            "total_revenue": _number(info.get("totalRevenue")),
            "gross_margin_current": gross_margin_current,
            "gross_margin_prior": gross_margin_prior,
            "debt_to_equity": _number(info.get("debtToEquity")),
            "analyst_revisions_available": analyst_available,
            "analyst_upgrades_90d": upgrades,
            "analyst_downgrades_90d": downgrades,
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
