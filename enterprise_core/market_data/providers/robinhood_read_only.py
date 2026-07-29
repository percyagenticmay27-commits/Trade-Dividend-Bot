"""Robinhood read-only adapter boundary.

The adapter accepts an injected history reader implemented by the validated
DigitalOcean Codex/Robinhood MCP runtime. It intentionally contains no account,
order, position, or capital-management methods.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Sequence

from ..models import MarketBar, MarketDataRequest, MarketDataResponse, ProviderStatus
from ..provider import MarketDataProvider

HistoryReader = Callable[[MarketDataRequest], Sequence[Mapping[str, Any]]]
HealthReader = Callable[[], bool]


class RobinhoodReadOnlyProvider(MarketDataProvider):
    name = "robinhood_read_only"
    priority = 20

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(
        self,
        history_reader: HistoryReader,
        health_reader: HealthReader | None = None,
    ) -> None:
        if not callable(history_reader):
            raise TypeError("history_reader must be callable")
        self._history_reader = history_reader
        self._health_reader = health_reader
        self._last_status = ProviderStatus.VERIFIED

    def health(self) -> ProviderStatus:
        if self._health_reader is None:
            return self._last_status
        try:
            return ProviderStatus.VERIFIED if self._health_reader() else ProviderStatus.UNAVAILABLE
        except Exception:
            return ProviderStatus.UNAVAILABLE

    def get_history(self, request: MarketDataRequest) -> MarketDataResponse:
        request.validate()
        try:
            rows = self._history_reader(request)
            bars = self._normalize(rows, request)
        except Exception as exc:
            self._last_status = ProviderStatus.UNAVAILABLE
            raise RuntimeError(f"Robinhood read-only history request failed: {exc}") from exc

        status = ProviderStatus.VERIFIED if bars else ProviderStatus.PARTIAL
        self._last_status = status
        warnings = () if bars else ("Robinhood returned no market bars",)
        return MarketDataResponse(
            request=request,
            bars=tuple(bars),
            provider=self.name,
            provider_status=status,
            warnings=warnings,
            metadata={
                "access_mode": "read_only",
                "execution_enabled": False,
                "transport": "injected_validated_runtime",
            },
        )

    @classmethod
    def _normalize(
        cls,
        rows: Sequence[Mapping[str, Any]],
        request: MarketDataRequest,
    ) -> list[MarketBar]:
        bars: list[MarketBar] = []
        for row in rows:
            timestamp = row.get("timestamp") or row.get("begins_at") or row.get("date")
            if timestamp is None:
                continue
            bar = MarketBar(
                symbol=str(row.get("symbol") or request.symbol).strip().upper(),
                timestamp=_normalize_timestamp(timestamp),
                open=float(_required(row, "open", "open_price")),
                high=float(_required(row, "high", "high_price")),
                low=float(_required(row, "low", "low_price")),
                close=float(_required(row, "close", "close_price")),
                volume=float(_optional(row, 0.0, "volume")),
                provider=cls.name,
                adjusted=bool(row.get("adjusted", False)),
                session=str(row.get("session") or "regular"),
                source_confidence=0.98,
            )
            bar.validate()
            bars.append(bar)
        bars.sort(key=lambda bar: bar.timestamp)
        if request.limit is not None:
            bars = bars[-request.limit :]
        return bars


def _required(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    raise ValueError(f"missing required market field: {'/'.join(keys)}")


def _optional(row: Mapping[str, Any], default: Any, *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value is not None:
            return value
    return default


def _normalize_timestamp(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    text = str(value).strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()
