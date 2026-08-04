from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import refresh_enterprise_market_data_normalized as production
from src.dividend_bot.enterprise_market_data_provider import MarketDataUnavailable
from src.dividend_bot.twelve_data_market_data_source import TwelveDataSource


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def test_quote_normalizes_twelve_data_response(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _Response({"symbol": "SOXL", "close": "140.25", "timestamp": "1785877200"}),
    )
    quote = TwelveDataSource("secret-key").get_quote("SOXL")
    assert quote["provider"] == "TWELVE_DATA"
    assert quote["price"] == 140.25
    assert quote["source_type"] == "LIVE_QUOTE"
    assert quote["quote_timestamp"].endswith("+00:00")


def test_history_normalizes_twelve_data_response(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _Response({
            "values": [
                {"datetime": "2026-08-03", "open": "138", "high": "141", "low": "137", "close": "140", "volume": "1000"},
                {"datetime": "2026-08-04", "open": "140", "high": "142", "low": "139", "close": "141", "volume": "1200"},
            ]
        }),
    )
    history = TwelveDataSource("secret-key").get_history("SOXL", "1mo", "1d")
    assert history["provider"] == "TWELVE_DATA"
    assert history["bars"][-1]["date"] == "2026-08-04"
    assert history["bars"][-1]["close"] == "141"


def test_error_does_not_leak_api_key(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda request, timeout: _Response({"status": "error", "code": 401, "message": "invalid key"}),
    )
    with pytest.raises(MarketDataUnavailable) as excinfo:
        TwelveDataSource("super-secret").get_quote("SOXL")
    assert "super-secret" not in str(excinfo.value)


def test_production_order_places_twelve_data_second():
    assert production.PRODUCTION_PROVIDER_ORDER == (
        "YFINANCE", "TWELVE_DATA", "LOCAL_CACHE", "ROBINHOOD_MCP"
    )


def test_builder_skips_twelve_data_without_key(monkeypatch, tmp_path):
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    provider = production.build_production_provider(tmp_path, tmp_path / "cache", None)
    assert [source.name for source in provider.sources] == ["YFINANCE", "LOCAL_CACHE"]


def test_builder_enables_twelve_data_with_key(monkeypatch, tmp_path):
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "configured")
    provider = production.build_production_provider(tmp_path, tmp_path / "cache", None)
    assert [source.name for source in provider.sources] == ["YFINANCE", "TWELVE_DATA", "LOCAL_CACHE"]


def test_systemd_uses_protected_environment_file():
    unit = open("deploy/systemd/enterprise-market-data-refresh.service", encoding="utf-8").read()
    assert "EnvironmentFile=-/etc/tradebot/enterprise-market-data.env" in unit
    assert "TWELVE_DATA_API_KEY=" not in unit
