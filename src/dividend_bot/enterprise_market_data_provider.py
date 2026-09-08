"""Enterprise AI CIO shared market-data provider (paper-only, read-only)."""
from __future__ import annotations

import csv
import json
import os
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Protocol

MODULE_NAME = "enterprise_market_data_provider"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
PROVIDER_ORDER = ("ROBINHOOD_MCP", "YFINANCE", "STOOQ", "LOCAL_CACHE")


class MarketDataUnavailable(RuntimeError):
    """Raised when no provider can supply a fresh normalized response."""


@dataclass(frozen=True)
class FreshnessPolicy:
    quote_max_age_seconds: int = 900
    daily_history_max_age_days: int = 5


@dataclass
class ProviderAttempt:
    provider: str
    success: bool
    stale: bool = False
    cache_used: bool = False
    error: str = ""
    latest_bar_date: str = ""
    quote_timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class MarketDataSource(Protocol):
    name: str
    def get_quote(self, symbol: str) -> dict[str, Any]: ...
    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]: ...


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_quote_stale(timestamp: str, policy: FreshnessPolicy, now: datetime) -> bool:
    return (now - _parse_dt(timestamp)).total_seconds() > policy.quote_max_age_seconds


def _is_history_stale(latest_bar_date: str, policy: FreshnessPolicy, now: datetime) -> bool:
    latest = date.fromisoformat(latest_bar_date)
    return (now.date() - latest).days > policy.daily_history_max_age_days


def _safe_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value or not all(ch.isalnum() or ch in ".-" for ch in value):
        raise ValueError("invalid symbol")
    return value


def _reject_conflicting_bars(bars: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for raw in bars:
        bar = dict(raw)
        key = str(bar.get("date", ""))
        if not key:
            raise ValueError("historical bar date is required")
        normalized = {
            "date": key,
            "open": float(bar["open"]),
            "high": float(bar["high"]),
            "low": float(bar["low"]),
            "close": float(bar["close"]),
            "adjusted_close": None if bar.get("adjusted_close") in (None, "") else float(bar["adjusted_close"]),
            "volume": int(float(bar.get("volume", 0))),
        }
        if normalized["high"] < normalized["low"]:
            raise ValueError(f"invalid high/low for {key}")
        previous = by_date.get(key)
        if previous is not None and previous != normalized:
            raise ValueError(f"conflicting duplicate bar for {key}")
        by_date[key] = normalized
    return [by_date[key] for key in sorted(by_date)]


class CodexRobinhoodSource:
    name = "ROBINHOOD_MCP"
    def __init__(self, bridge: Callable[[str, str, str, str], dict[str, Any]]) -> None:
        self._bridge = bridge
    def get_quote(self, symbol: str) -> dict[str, Any]:
        return self._bridge("get_quote", symbol, "", "")
    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        return self._bridge("get_history", symbol, period, interval)


class YFinanceSource:
    name = "YFINANCE"
    def _ticker(self, symbol: str):
        try:
            import yfinance as yf  # type: ignore
        except ImportError as exc:
            raise MarketDataUnavailable("yfinance is not installed") from exc
        return yf.Ticker(symbol)
    def get_quote(self, symbol: str) -> dict[str, Any]:
        ticker = self._ticker(symbol)
        history = ticker.history(period="2d", interval="1m", auto_adjust=False)
        if history.empty:
            raise MarketDataUnavailable("yfinance returned no quote rows")
        row = history.iloc[-1]
        ts = history.index[-1].to_pydatetime().astimezone(timezone.utc).isoformat()
        return {"symbol": symbol, "price": float(row["Close"]), "quote_timestamp": ts,
                "trading_date": ts[:10], "provider": self.name, "source_type": "LIVE_QUOTE",
                "confidence": 0.90, "warnings": []}
    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        frame = self._ticker(symbol).history(period=period, interval=interval, auto_adjust=False, actions=True)
        if frame.empty:
            raise MarketDataUnavailable("yfinance returned no history rows")
        bars = []
        for index, row in frame.iterrows():
            bars.append({"date": index.date().isoformat(), "open": row["Open"], "high": row["High"],
                         "low": row["Low"], "close": row["Close"],
                         "adjusted_close": row.get("Adj Close"), "volume": row.get("Volume", 0)})
        splits = [{"date": idx.date().isoformat(), "ratio": float(value)}
                  for idx, value in frame.get("Stock Splits", []).items() if float(value)] if "Stock Splits" in frame else []
        dividends = [{"date": idx.date().isoformat(), "amount": float(value)}
                     for idx, value in frame.get("Dividends", []).items() if float(value)] if "Dividends" in frame else []
        return {"symbol": symbol, "interval": interval, "period": period, "provider": self.name,
                "generated_at": utc_now().isoformat(), "corporate_action_adjusted": False,
                "split_history": splits, "dividend_history": dividends, "bars": bars, "warnings": []}


class StooqSource:
    name = "STOOQ"
    def _history(self, symbol: str) -> list[dict[str, Any]]:
        query = urllib.parse.urlencode({"s": f"{symbol.lower()}.us", "i": "d"})
        url = f"https://stooq.com/q/d/l/?{query}"
        with urllib.request.urlopen(url, timeout=15) as response:
            text = response.read().decode("utf-8")
        rows = list(csv.DictReader(text.splitlines()))
        if not rows or "Close" not in rows[0]:
            raise MarketDataUnavailable("Stooq returned no usable rows")
        return [{"date": row["Date"], "open": row["Open"], "high": row["High"], "low": row["Low"],
                 "close": row["Close"], "adjusted_close": None, "volume": row.get("Volume", 0)} for row in rows]
    def get_quote(self, symbol: str) -> dict[str, Any]:
        bar = self._history(symbol)[-1]
        ts = f"{bar['date']}T21:00:00+00:00"
        return {"symbol": symbol, "price": float(bar["close"]), "quote_timestamp": ts,
                "trading_date": bar["date"], "provider": self.name, "source_type": "LATEST_DAILY_CLOSE",
                "confidence": 0.70, "warnings": ["Stooq quote is latest daily close"]}
    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        if interval != "1d":
            raise MarketDataUnavailable("Stooq Version 1 supports interval=1d only")
        return {"symbol": symbol, "interval": interval, "period": period, "provider": self.name,
                "generated_at": utc_now().isoformat(), "corporate_action_adjusted": False,
                "split_history": [], "dividend_history": [], "bars": self._history(symbol),
                "warnings": ["Adjusted close and corporate actions unavailable from Stooq fallback"]}


class LocalCacheSource:
    name = "LOCAL_CACHE"
    def __init__(self, cache_dir: Path) -> None:
        self.cache_dir = cache_dir
    def _read(self, operation: str, symbol: str) -> dict[str, Any]:
        path = self.cache_dir / f"{symbol}.{operation}.json"
        if not path.is_file():
            raise MarketDataUnavailable("cache entry not found")
        return json.loads(path.read_text(encoding="utf-8"))
    def get_quote(self, symbol: str) -> dict[str, Any]: return self._read("quote", symbol)
    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]: return self._read("history", symbol)


@dataclass
class EnterpriseMarketDataProvider:
    sources: list[MarketDataSource]
    results_dir: Path
    cache_dir: Path
    freshness: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    now_fn: Callable[[], datetime] = utc_now
    attempts: list[ProviderAttempt] = field(default_factory=list)

    def _normalize_quote(self, symbol: str, raw: dict[str, Any], provider: str, cache_used: bool) -> dict[str, Any]:
        ts = str(raw["quote_timestamp"])
        stale = _is_quote_stale(ts, self.freshness, self.now_fn())
        result = {"symbol": symbol, "price": float(raw["price"]), "quote_timestamp": ts,
                  "trading_date": str(raw.get("trading_date") or ts[:10]), "provider": provider,
                  "source_type": str(raw.get("source_type", "QUOTE")), "stale": stale,
                  "confidence": float(raw.get("confidence", 0.5)), "warnings": list(raw.get("warnings", [])),
                  "cache_used": cache_used}
        if result["price"] <= 0: raise ValueError("price must be positive")
        return result

    def _normalize_history(self, symbol: str, period: str, interval: str, raw: dict[str, Any], provider: str, cache_used: bool) -> dict[str, Any]:
        bars = _reject_conflicting_bars(raw.get("bars", []))
        if not bars: raise ValueError("history contains no bars")
        latest = bars[-1]["date"]
        stale = _is_history_stale(latest, self.freshness, self.now_fn())
        return {"symbol": symbol, "interval": interval, "period": period, "provider": provider,
                "generated_at": str(raw.get("generated_at") or self.now_fn().isoformat()),
                "latest_bar_date": latest, "stale": stale,
                "corporate_action_adjusted": bool(raw.get("corporate_action_adjusted", False)),
                "split_history": list(raw.get("split_history", [])),
                "dividend_history": list(raw.get("dividend_history", [])), "bars": bars,
                "warnings": list(raw.get("warnings", [])), "cache_used": cache_used}

    def _write_cache(self, operation: str, symbol: str, payload: dict[str, Any]) -> None:
        atomic_write_text(self.cache_dir / f"{symbol}.{operation}.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _resolve(self, operation: str, symbol: str, period: str = "1mo", interval: str = "1d") -> dict[str, Any]:
        symbol = _safe_symbol(symbol)
        self.attempts = []
        errors: list[str] = []
        for source in self.sources:
            cache_used = source.name == "LOCAL_CACHE"
            try:
                raw = source.get_quote(symbol) if operation == "quote" else source.get_history(symbol, period, interval)
                normalized = (self._normalize_quote(symbol, raw, source.name, cache_used) if operation == "quote"
                              else self._normalize_history(symbol, period, interval, raw, source.name, cache_used))
                self.attempts.append(ProviderAttempt(source.name, True, normalized["stale"], cache_used,
                                                     latest_bar_date=normalized.get("latest_bar_date", ""),
                                                     quote_timestamp=normalized.get("quote_timestamp", "")))
                if normalized["stale"]:
                    errors.append(f"{source.name}: stale data rejected")
                    continue
                if not cache_used:
                    self._write_cache(operation, symbol, normalized)
                self._write_evidence(symbol, operation, normalized, errors)
                return normalized
            except Exception as exc:
                message = f"{source.name}: {type(exc).__name__}: {exc}"
                errors.append(message)
                self.attempts.append(ProviderAttempt(source.name, False, cache_used=cache_used, error=message))
        self._write_evidence(symbol, operation, None, errors)
        raise MarketDataUnavailable("; ".join(errors))

    def get_quote(self, symbol: str) -> dict[str, Any]: return self._resolve("quote", symbol)
    def get_history(self, symbol: str, period: str = "1mo", interval: str = "1d") -> dict[str, Any]: return self._resolve("history", symbol, period, interval)
    def get_latest_close(self, symbol: str) -> float: return float(self.get_history(symbol)["bars"][-1]["close"])
    def get_previous_close(self, symbol: str) -> float:
        bars = self.get_history(symbol)["bars"]
        if len(bars) < 2: raise MarketDataUnavailable("previous close unavailable")
        return float(bars[-2]["close"])
    def get_volume(self, symbol: str) -> int: return int(self.get_history(symbol)["bars"][-1]["volume"])
    def get_split_history(self, symbol: str) -> list[dict[str, Any]]: return list(self.get_history(symbol)["split_history"])
    def get_dividend_history(self, symbol: str) -> list[dict[str, Any]]: return list(self.get_history(symbol)["dividend_history"])

    def refresh_strategy(self, strategy_id: str, required_symbols: Iterable[str], optional_symbols: Iterable[str]) -> dict[str, Any]:
        records, warnings, errors = [], [], []
        for required, symbols in ((True, required_symbols), (False, optional_symbols)):
            for symbol in symbols:
                try:
                    quote = self.get_quote(symbol)
                    records.append({"strategy_id": strategy_id, "symbol": symbol.upper(), "required": required,
                                    "status": "FRESH", "provider": quote["provider"], "price": quote["price"],
                                    "quote_timestamp": quote["quote_timestamp"]})
                except MarketDataUnavailable as exc:
                    target = errors if required else warnings
                    target.append(f"{symbol.upper()}: {exc}")
                    records.append({"strategy_id": strategy_id, "symbol": symbol.upper(), "required": required,
                                    "status": "BLOCKED" if required else "WARNING", "provider": "NONE"})
        status = "BLOCKED" if errors else ("WARNING" if warnings else "READY")
        return {"strategy_id": strategy_id, "status": status, "records": records, "warnings": warnings, "errors": errors}

    def _write_evidence(self, symbol: str, operation: str, result: dict[str, Any] | None, errors: list[str]) -> None:
        generated = self.now_fn().isoformat()
        status = {"module": MODULE_NAME, "module_version": MODULE_VERSION, "schema_version": SCHEMA_VERSION,
                  "generated_at": generated, "symbol": symbol, "operation": operation,
                  "status": "FRESH" if result else "BLOCKED", "provider_attempt_order": list(PROVIDER_ORDER),
                  "successful_provider": result.get("provider") if result else None,
                  "attempts": [attempt.to_dict() for attempt in self.attempts], "warnings": result.get("warnings", []) if result else [],
                  "errors": errors, "paper_trade_mode": True, "live_trading_enabled": False,
                  "broker_execution_enabled": False, "order_placement_enabled": False, "capital_movement_enabled": False}
        health = {"generated_at": generated, "providers": [attempt.to_dict() for attempt in self.attempts],
                  "healthy": bool(result), "secrets_written": False, "safety": {"paper_only": True, "read_only": True}}
        contract = {"schema_version": SCHEMA_VERSION, "provider_precedence": list(PROVIDER_ORDER),
                    "quote_fields": ["symbol","price","quote_timestamp","trading_date","provider","source_type","stale","confidence","warnings"],
                    "history_fields": ["symbol","interval","period","provider","generated_at","latest_bar_date","stale","corporate_action_adjusted","bars"],
                    "operations": ["get_quote","get_history","get_latest_close","get_previous_close","get_volume","get_split_history","get_dividend_history"]}
        atomic_write_text(self.results_dir / "enterprise_market_data_status.json", json.dumps(status, indent=2, sort_keys=True) + "\n")
        atomic_write_text(self.results_dir / "enterprise_market_data_provider_health.json", json.dumps(health, indent=2, sort_keys=True) + "\n")
        atomic_write_text(self.results_dir / "enterprise_market_data_contract.json", json.dumps(contract, indent=2, sort_keys=True) + "\n")
        row = {"generated_at": generated, "symbol": symbol, "operation": operation,
               "status": status["status"], "provider": status["successful_provider"] or "",
               "latest_bar_date": result.get("latest_bar_date", "") if result else "",
               "quote_timestamp": result.get("quote_timestamp", "") if result else "",
               "cache_used": result.get("cache_used", False) if result else False,
               "errors": " | ".join(errors)}
        csv_path = self.results_dir / "enterprise_market_data_refresh.csv"
        header = list(row)
        prior = []
        if csv_path.is_file():
            prior = list(csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines()))
        lines = [",".join(header)]
        for item in [*prior, row]:
            lines.append(",".join('"' + str(item.get(key, "")).replace('"', '""') + '"' for key in header))
        atomic_write_text(csv_path, "\n".join(lines) + "\n")


def build_default_provider(results_dir: Path, cache_dir: Path, codex_bridge: Callable[[str, str, str, str], dict[str, Any]] | None = None) -> EnterpriseMarketDataProvider:
    sources: list[MarketDataSource] = []
    if codex_bridge is not None:
        sources.append(CodexRobinhoodSource(codex_bridge))
    sources.extend([YFinanceSource(), StooqSource(), LocalCacheSource(cache_dir)])
    return EnterpriseMarketDataProvider(sources=sources, results_dir=results_dir, cache_dir=cache_dir)
