from __future__ import annotations

import csv
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
            "price": 42.0,
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
            "corporate_action_adjusted": True,
            "split_history": [{"date": "2026-07-01", "ratio": 2.0}],
            "dividend_history": [],
            "warnings": [],
            "bars": [
                {
                    "date": "2026-08-03",
                    "open": 10.0,
                    "high": 12.0,
                    "low": 9.0,
                    "close": 11.0,
                    "adjusted_close": 11.0,
                    "volume": 100,
                },
                {
                    "date": "2026-08-04",
                    "open": 11.0,
                    "high": 13.0,
                    "low": 10.0,
                    "close": 12.0,
                    "adjusted_close": 12.0,
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


def test_history_json_export_contains_full_normalized_bars(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)
    result = refresh_strategy_market_data(provider, "SWING-001", ["SOXL"], [])

    path = tmp_path / "results" / "enterprise_market_data_history" / "SOXL.history.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["strategy_id"] == "SWING-001"
    assert payload["symbol"] == "SOXL"
    assert payload["stale"] is False
    assert payload["latest_bar_date"] == "2026-08-04"
    assert len(payload["bars"]) == 2
    assert payload["bars"][-1]["close"] == 12.0
    assert result["records"][0]["history"]["bars_json_path"] == str(path)


def test_history_csv_export_is_swing_sync_compatible(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)
    result = refresh_strategy_market_data(provider, "SWING-001", ["TQQQ"], [])

    path = tmp_path / "results" / "enterprise_market_data_history" / "TQQQ.csv"
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert list(rows[0]) == [
        "date", "open", "high", "low", "close", "adjusted_close", "volume"
    ]
    assert rows[-1]["date"] == "2026-08-04"
    assert rows[-1]["close"] == "12.0"
    assert rows[-1]["volume"] == "200"
    assert result["records"][0]["history"]["bars_csv_path"] == str(path)


def test_contract_publishes_history_export_patterns(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)
    refresh_strategy_market_data(provider, "SWING-001", ["SOXL", "TQQQ"], [])

    contract = json.loads(
        (tmp_path / "results" / "enterprise_market_data_contract.json").read_text()
    )
    exports = contract["history_exports"]
    assert exports["directory"] == "enterprise_market_data_history"
    assert exports["json_pattern"] == "{symbol}.history.json"
    assert exports["csv_pattern"] == "{symbol}.csv"
    assert exports["atomic_writes"] is True


def test_status_contains_export_paths_for_all_required_symbols(tmp_path: Path) -> None:
    provider = build_provider(tmp_path)
    result = refresh_strategy_market_data(provider, "SWING-001", ["SOXL", "TQQQ"], [])

    assert result["status"] == "READY"
    assert len(result["records"]) == 2
    for record in result["records"]:
        history = record["history"]
        assert Path(history["bars_json_path"]).exists()
        assert Path(history["bars_csv_path"]).exists()
