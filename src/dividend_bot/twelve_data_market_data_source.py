"""Twelve Data market-data source for the Enterprise AI CIO provider.

Read-only and strategy-neutral. The API key is supplied at runtime and is never
included in normalized payloads, evidence files, or error messages.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from src.dividend_bot.enterprise_market_data_provider import MarketDataUnavailable, utc_now


class TwelveDataSource:
    name = "TWELVE_DATA"
    base_url = "https://api.twelvedata.com"

    def __init__(self, api_key: str, timeout_seconds: int = 20) -> None:
        key = api_key.strip()
        if not key:
            raise ValueError("Twelve Data API key is required")
        self._api_key = key
        self._timeout_seconds = timeout_seconds

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        safe_params = dict(params)
        request_params = {**safe_params, "apikey": self._api_key}
        url = f"{self.base_url}/{endpoint}?{urllib.parse.urlencode(request_params)}"
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "TradeBotEnterpriseMarketData/1.0"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                raise MarketDataUnavailable("TWELVE_DATA_RATE_LIMITED") from exc
            if exc.code in (401, 403):
                raise MarketDataUnavailable("TWELVE_DATA_AUTH_FAILED") from exc
            raise MarketDataUnavailable(f"TWELVE_DATA_HTTP_{exc.code}") from exc
        except urllib.error.URLError as exc:
            raise MarketDataUnavailable("TWELVE_DATA_UPSTREAM_UNAVAILABLE") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MarketDataUnavailable("TWELVE_DATA_INVALID_JSON") from exc

        if not isinstance(payload, dict):
            raise MarketDataUnavailable("TWELVE_DATA_INVALID_RESPONSE")
        if payload.get("status") == "error" or payload.get("code"):
            code = payload.get("code", "UNKNOWN")
            message = str(payload.get("message", "request failed"))
            # Do not echo request URLs or API keys.
            raise MarketDataUnavailable(f"TWELVE_DATA_API_ERROR_{code}: {message}")
        return payload

    @staticmethod
    def _iso_timestamp(value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()

    def get_quote(self, symbol: str) -> dict[str, Any]:
        payload = self._request("quote", {"symbol": symbol})
        price = payload.get("close") or payload.get("price")
        timestamp = payload.get("timestamp") or payload.get("datetime")
        if price in (None, "") or timestamp in (None, ""):
            raise MarketDataUnavailable("TWELVE_DATA_QUOTE_FIELDS_MISSING")
        if str(timestamp).isdigit():
            quote_timestamp = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()
        else:
            quote_timestamp = self._iso_timestamp(str(timestamp))
        return {
            "symbol": symbol,
            "price": float(price),
            "quote_timestamp": quote_timestamp,
            "trading_date": quote_timestamp[:10],
            "provider": self.name,
            "source_type": "LIVE_QUOTE",
            "confidence": 0.88,
            "warnings": [],
        }

    def get_history(self, symbol: str, period: str, interval: str) -> dict[str, Any]:
        interval_map = {"1d": "1day", "1h": "1h", "30m": "30min", "15m": "15min", "5m": "5min", "1m": "1min"}
        td_interval = interval_map.get(interval)
        if td_interval is None:
            raise MarketDataUnavailable(f"TWELVE_DATA_UNSUPPORTED_INTERVAL_{interval}")
        outputsize_map = {"5d": 10, "1mo": 40, "3mo": 100, "6mo": 190, "1y": 370, "2y": 740, "5y": 1900}
        outputsize = outputsize_map.get(period, 500)
        payload = self._request(
            "time_series",
            {
                "symbol": symbol,
                "interval": td_interval,
                "outputsize": outputsize,
                "order": "ASC",
                "timezone": "UTC",
            },
        )
        values = payload.get("values")
        if not isinstance(values, list) or not values:
            raise MarketDataUnavailable("TWELVE_DATA_NO_HISTORY_ROWS")
        bars = []
        for row in values:
            bars.append(
                {
                    "date": str(row["datetime"])[:10],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "adjusted_close": None,
                    "volume": row.get("volume", 0),
                }
            )
        return {
            "symbol": symbol,
            "interval": interval,
            "period": period,
            "provider": self.name,
            "generated_at": utc_now().isoformat(),
            "corporate_action_adjusted": False,
            "split_history": [],
            "dividend_history": [],
            "bars": bars,
            "warnings": ["Twelve Data history is normalized OHLCV; adjusted close and corporate actions are not supplied by this fallback."],
        }
