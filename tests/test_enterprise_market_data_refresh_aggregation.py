from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from refresh_enterprise_market_data import refresh_strategy_market_data
from src.dividend_bot.enterprise_market_data_provider import (
    EnterpriseMarketDataProvider,
    FreshnessPolicy,
)

NOW = datetime(2026, 8, 4, 17, 0, tzinfo=timezone.utc)


class Source:
    name = "YFINANCE"

    def get_quote(self, symbol: str):
        return {
            "symbol": symbol,
            "price": 40.0 if symbol == "SOXL" else 90.0,
            "quote_timestamp": "2026-08-04T16:59:00+00:00",
            "trading_date": "2026-08-04",
            "provider": self.name,
            "source_type": "LIVE_QUOTE",
            "confidence": 0.9,
            "warnings": [],
        }

    def get_history(self, symbol: str, period: str, interval: str):
        return {
            "symbol": symbol,
            "period": period,
            "interval": interval,
            "provider": self.name,
            "generated_at": NOW.isoformat(),
            "corporate_action_adjusted": False,
            "split_history": [],
            "dividend_history": [],
            "warnings": [],
            "bars": [
                {
                    "date": "2026-08-03",
                    "open": 10,
                    "high": 12,
                    "low": 9,
                    "close": 11,
                    "adjusted_close": 11,
                    "volume": 100,
                },
                {
                    "date": "2026-08-04",
                    "open": 11,
                    "high": 13,
                    "low": 10,
                    "close": 12,
                    "adjusted_close": 12,
                    "volume": 200,
                },
            ],
        }


def build_provider(tmp_path: Path) -> EnterpriseMarketDataProvider:
    return EnterpriseMarketDataProvider(
        sources=[Source()],
        results_dir=tmp_path / "results",
        cache_dir=tmp_path / "cache",
        freshness=FreshnessPolicy(),
        now_fn=lambda: NOW,
    )


def test_refresh_aggregates_quotes_and_history_for_all_required_symbols(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)

    result = refresh_strategy_market_data(
        provider,
        "SWING-001",
        ["SOXL", "TQQQ"],
        [],
    )

    assert result["status"] == "READY"
    assert [record["symbol"] for record in result["records"]] == ["SOXL", "TQQQ"]
    for record in result["records"]:
        assert record["quote"]["provider"] == "YFINANCE"
        assert record["history"]["provider"] == "YFINANCE"
        assert record["history"]["latest_bar_date"] == "2026-08-04"
        assert record["history"]["bar_count"] == 2


def test_status_json_is_strategy_level_not_last_symbol_wins(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)
    refresh_strategy_market_data(provider, "SWING-001", ["SOXL", "TQQQ"], [])

    status = json.loads(
        (tmp_path / "results" / "enterprise_market_data_status.json").read_text()
    )

    assert status["strategy_id"] == "SWING-001"
    assert status["status"] == "READY"
    assert {record["symbol"] for record in status["records"]} == {"SOXL", "TQQQ"}
    assert all(record["quote"] for record in status["records"])
    assert all(record["history"] for record in status["records"])


def test_provider_health_reports_quote_and_history_attempts_per_symbol(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)
    refresh_strategy_market_data(provider, "SWING-001", ["SOXL", "TQQQ"], [])

    health = json.loads(
        (tmp_path / "results" / "enterprise_market_data_provider_health.json").read_text()
    )

    assert health["healthy"] is True
    assert len(health["symbols"]) == 2
    for symbol in health["symbols"]:
        assert symbol["quote_provider"] == "YFINANCE"
        assert symbol["history_provider"] == "YFINANCE"
        assert symbol["quote_attempts"]
        assert symbol["history_attempts"]
        assert symbol["latest_bar_date"] == "2026-08-04"


def test_required_history_failure_blocks_only_requesting_strategy(tmp_path: Path) -> None:
    class QuoteOnlySource(Source):
        def get_history(self, symbol: str, period: str, interval: str):
            raise RuntimeError("history unavailable")

    provider = EnterpriseMarketDataProvider(
        sources=[QuoteOnlySource()],
        results_dir=tmp_path / "results",
        cache_dir=tmp_path / "cache",
        freshness=FreshnessPolicy(),
        now_fn=lambda: NOW,
    )

    result = refresh_strategy_market_data(provider, "SWING-001", ["SOXL"], [])

    assert result["strategy_id"] == "SWING-001"
    assert result["status"] == "BLOCKED"
    assert result["records"][0]["quote"] is not None
    assert result["records"][0]["history"] is None
    assert "history" in result["errors"][0]
