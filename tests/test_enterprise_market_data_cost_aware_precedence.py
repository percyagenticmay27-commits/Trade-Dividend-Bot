from __future__ import annotations

from pathlib import Path

import refresh_enterprise_market_data as refresh
from refresh_robinhood_fallback_handoffs import unresolved_operations


def test_routine_market_data_precedence_is_public_cache_then_robinhood(tmp_path: Path) -> None:
    provider = refresh.build_cost_aware_provider(tmp_path / "results", tmp_path / "cache", lambda *_: {})
    assert [source.name for source in provider.sources] == [
        "YFINANCE",
        "STOOQ",
        "LOCAL_CACHE",
        "ROBINHOOD_MCP",
    ]
    assert list(refresh.MARKET_DATA_PROVIDER_ORDER) == [
        "YFINANCE",
        "STOOQ",
        "LOCAL_CACHE",
        "ROBINHOOD_MCP",
    ]


def test_public_only_pass_has_no_robinhood_source(tmp_path: Path) -> None:
    provider = refresh.build_cost_aware_provider(tmp_path / "results", tmp_path / "cache", None)
    assert [source.name for source in provider.sources] == ["YFINANCE", "STOOQ", "LOCAL_CACHE"]


def test_robinhood_fallback_skipped_when_public_pass_is_ready() -> None:
    status = {
        "records": [
            {"symbol": "SOXL", "quote": {"provider": "YFINANCE"}, "history": {"provider": "YFINANCE"}},
            {"symbol": "TQQQ", "quote": {"provider": "STOOQ"}, "history": {"provider": "LOCAL_CACHE"}},
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
    assert refresh.MARKET_DATA_PROVIDER_ORDER[-1] == "ROBINHOOD_MCP"
