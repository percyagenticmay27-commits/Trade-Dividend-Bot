"""Yahoo Finance read-only historical market data adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..models import MarketBar, MarketDataRequest, MarketDataResponse, ProviderStatus
from ..provider import MarketDataProvider

JsonLoader = Callable[[str, float], dict[str, Any]]


class YahooFinanceProvider(MarketDataProvider):
    """Retrieve normalized OHLCV history from Yahoo's public chart endpoint."""

    name = "yahoo_finance"
    priority = 10

    def __init__(self, timeout_seconds: float = 10.0, loader: JsonLoader | None = None):
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self.timeout_seconds = timeout_seconds
        self._loader = loader or self._load_json
        self._last_status = ProviderStatus.VERIFIED

    def health(self) -> ProviderStatus:
        return self._last_status

    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        request.validate()
        url = self._build_url(request)
        try:
            payload = self._loader(url, self.timeout_seconds)
            bars = self._normalize(payload, request)
        except Exception as exc:
            self._last_status = ProviderStatus.UNAVAILABLE
            raise RuntimeError(f"Yahoo Finance history request failed: {exc}") from exc

        status = ProviderStatus.VERIFIED if bars else ProviderStatus.PARTIAL
        self._last_status = status
        warnings = () if bars else ("Yahoo Finance returned no market bars",)
        return MarketDataResponse(
            request=request,
            bars=tuple(bars),
            provider=self.name,
            provider_status=status,
            warnings=warnings,
            metadata={"source": "query1.finance.yahoo.com/v8/finance/chart"},
        )

    @staticmethod
    def _load_json(url: str, timeout_seconds: float) -> dict[str, Any]:
        request = Request(url, headers={"User-Agent": "Enterprise-Trade-Platform/1.0"})
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _build_url(request: MarketDataRequest) -> str:
        params: dict[str, str] = {
            "interval": request.interval,
            "events": "div,splits",
            "includeAdjustedClose": "true",
        }
        if request.start:
            params["period1"] = str(_to_epoch(request.start))
        else:
            params["range"] = "1y"
        if request.end:
            params["period2"] = str(_to_epoch(request.end))
        return (
            "https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{quote(request.symbol.strip().upper())}?{urlencode(params)}"
        )

    @staticmethod
    def _normalize(payload: dict[str, Any], request: MarketDataRequest) -> list[MarketBar]:
        chart = payload.get("chart") or {}
        if chart.get("error"):
            raise ValueError(str(chart["error"]))
        results = chart.get("result") or []
        if not results:
            return []
        result = results[0]
        timestamps = result.get("timestamp") or []
        indicators = result.get("indicators") or {}
        quotes = indicators.get("quote") or []
        quote_data = quotes[0] if quotes else {}
        adjclose_rows = indicators.get("adjclose") or []
        adjclose = (adjclose_rows[0].get("adjclose") or []) if adjclose_rows else []

        bars: list[MarketBar] = []
        for index, timestamp in enumerate(timestamps):
            values = {
                key: _at(quote_data.get(key) or [], index)
                for key in ("open", "high", "low", "close", "volume")
            }
            if any(values[key] is None for key in ("open", "high", "low", "close")):
                continue
            bar = MarketBar(
                symbol=request.symbol.strip().upper(),
                timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
                open=float(values["open"]),
                high=float(values["high"]),
                low=float(values["low"]),
                close=float(values["close"]),
                volume=float(values["volume"] or 0.0),
                provider=YahooFinanceProvider.name,
                adjusted=bool(adjclose and _at(adjclose, index) is not None),
                session="regular",
                source_confidence=0.95,
            )
            bar.validate()
            bars.append(bar)

        if request.limit is not None:
            bars = bars[-request.limit :]
        return bars


def _at(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def _to_epoch(value: str) -> int:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp())
