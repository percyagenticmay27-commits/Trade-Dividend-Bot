from __future__ import annotations

from pathlib import Path

import refresh_enterprise_market_data_normalized as refresh
from refresh_robinhood_fallback_handoffs import unresolved_operations


def test_operation_aware_market_data_precedence(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-key")
    provider = refresh.build_market_data_provider(
        tmp_path / "results",
        tmp_path / "cache",
        lambda *_: {},
    )
    assert [source.name for source in provider.quote_sources] == [
        "YFINANCE",
        "TWELVE_DATA",
        "ROBINHOOD_MCP",
        "LOCAL_CACHE",
    ]
    assert [source.name for source in provider.history_sources] == [
        "YFINANCE",
        "TWELVE_DATA",
        "LOCAL_CACHE",
        "ROBINHOOD_MCP",
    ]
    assert list(refresh.QUOTE_PROVIDER_ORDER) == [
        "YFINANCE",
        "TWELVE_DATA",
        "ROBINHOOD_MCP",
        "LOCAL_CACHE",
    ]
    assert list(refresh.HISTORY_PROVIDER_ORDER) == [
        "YFINANCE",
        "TWELVE_DATA",
        "LOCAL_CACHE",
        "ROBINHOOD_MCP",
    ]


def test_public_only_pass_has_no_robinhood_source(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("TWELVE_DATA_API_KEY", "test-key")
    provider = refresh.build_market_data_provider(
        tmp_path / "results",
        tmp_path / "cache",
        lambda *_: {},
        public_only=True,
    )
    expected = ["YFINANCE", "TWELVE_DATA", "LOCAL_CACHE"]
    assert [source.name for source in provider.quote_sources] == expected
    assert [source.name for source in provider.history_sources] == expected


def test_builder_skips_twelve_data_without_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    provider = refresh.build_market_data_provider(
        tmp_path / "results",
        tmp_path / "cache",
        None,
        public_only=True,
    )
    assert [source.name for source in provider.quote_sources] == ["YFINANCE", "LOCAL_CACHE"]
    assert [source.name for source in provider.history_sources] == ["YFINANCE", "LOCAL_CACHE"]


def test_cache_remains_subject_to_strict_freshness_policy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TWELVE_DATA_API_KEY", raising=False)
    provider = refresh.build_market_data_provider(
        tmp_path / "results",
        tmp_path / "cache",
        None,
        public_only=True,
    )
    assert provider.freshness.quote_max_age_seconds == 900
    assert provider.freshness.daily_history_max_age_days == 5
    assert provider.quote_sources[-1].name == "LOCAL_CACHE"
    assert provider.history_sources[-1].name == "LOCAL_CACHE"


def test_robinhood_fallback_skipped_when_public_pass_is_ready() -> None:
    status = {
        "records": [
            {"symbol": "SOXL", "quote": {"provider": "YFINANCE"}, "history": {"provider": "YFINANCE"}},
            {"symbol": "TQQQ", "quote": {"provider": "TWELVE_DATA"}, "history": {"provider": "LOCAL_CACHE"}},
        ]
    }
    assert unresolved_operations(status) == []


def test_robinhood_fallback_requests_only_missing_operations() -> None:
    status = {
        "records": [
            {"symbol": "SOXL", "quote": None, "history": {"provider": "YFINANCE"}},
            {"symbol": "TQQQ", "quote": {"provider": "YFINANCE"}, "history": None},
        ]
    }
    assert unresolved_operations(status) == [
        ("get_quote", "SOXL"),
        ("get_history", "TQQQ"),
    ]


def test_systemd_uses_two_pass_conditional_robinhood_policy() -> None:
    unit = Path("deploy/systemd/enterprise-market-data-refresh.service").read_text(encoding="utf-8")
    assert "--disable-robinhood --always-zero" in unit
    assert "refresh_robinhood_fallback_handoffs.py" in unit
    assert "root_codex_market_data_handoff.py --operation" not in unit
    assert unit.count("ExecStart=") == 3


def test_contract_policy_is_cost_aware() -> None:
    assert refresh.QUOTE_PROVIDER_ORDER[-2:] == ("ROBINHOOD_MCP", "LOCAL_CACHE")
    assert refresh.HISTORY_PROVIDER_ORDER[-2:] == ("LOCAL_CACHE", "ROBINHOOD_MCP")
