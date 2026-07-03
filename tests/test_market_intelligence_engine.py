"""
Pytest coverage for market_intelligence_engine.py.

These tests verify the read-only Market Intelligence Engine without modifying
runtime workflow files, portfolio logic, dividend logic, asset registry logic,
market regime logic, or broker state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import market_intelligence_engine as intelligence


def test_module_constants_are_expected():
    assert intelligence.MODULE_NAME == "market_intelligence_engine"
    assert intelligence.MODULE_VERSION == "1.0.0"
    assert intelligence.SCHEMA_VERSION == "1.0"
    assert intelligence.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_public_dataclasses_exist():
    assert hasattr(intelligence, "MarketIntelligenceSignal")
    assert hasattr(intelligence, "MarketIntelligenceReport")


def test_required_public_functions_exist_and_are_callable():
    assert callable(intelligence.build_market_intelligence_report)
    assert callable(intelligence.validate_market_intelligence_report)
    assert callable(intelligence.write_market_intelligence_report_json)
    assert callable(intelligence.read_market_intelligence_report_json)
    assert callable(intelligence.format_market_intelligence_report_markdown)
    assert callable(intelligence.write_market_intelligence_report_markdown)


def test_build_market_intelligence_report_returns_valid_payload():
    payload = intelligence.build_market_intelligence_report()

    assert intelligence.validate_market_intelligence_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["module_name"] == intelligence.MODULE_NAME
    assert payload["module_version"] == intelligence.MODULE_VERSION
    assert payload["schema_version"] == intelligence.SCHEMA_VERSION
    assert payload["generated_by"] == intelligence.GENERATED_BY


def test_report_required_fields_exist():
    payload = intelligence.build_market_intelligence_report()

    for field in intelligence.REPORT_REQUIRED_FIELDS:
        assert field in payload


def test_signal_required_fields_exist():
    payload = intelligence.build_market_intelligence_report()

    for signal in payload["intelligence_signals"]:
        for field in intelligence.SIGNAL_REQUIRED_FIELDS:
            assert field in signal


def test_supported_intelligence_statuses_match_approved_list():
    payload = intelligence.build_market_intelligence_report()

    expected = [
        "STRONGLY_POSITIVE",
        "POSITIVE",
        "NEUTRAL",
        "NEGATIVE",
        "STRONGLY_NEGATIVE",
        "MIXED",
        "UNKNOWN",
    ]

    assert payload["supported_intelligence_statuses"] == expected
    assert intelligence.SUPPORTED_INTELLIGENCE_STATUSES == expected


def test_intelligence_categories_match_approved_list():
    payload = intelligence.build_market_intelligence_report()

    expected = [
        "market_trend",
        "sector_strength",
        "volatility_context",
        "liquidity_context",
        "breadth_context",
        "macro_context",
        "earnings_risk_context",
        "news_risk_context",
        "dividend_income_context",
        "leveraged_etf_risk_context",
    ]

    assert payload["intelligence_categories"] == expected
    assert intelligence.INTELLIGENCE_CATEGORIES == expected


def test_default_overall_behavior():
    payload = intelligence.build_market_intelligence_report()

    assert payload["overall_intelligence_score"] == 0
    assert payload["overall_confidence"] == 0.0
    assert payload["overall_confidence_level"] == "LOW"
    assert payload["overall_intelligence_status"] == "UNKNOWN"


def test_default_signal_behavior():
    payload = intelligence.build_market_intelligence_report()

    assert len(payload["intelligence_signals"]) == len(intelligence.INTELLIGENCE_CATEGORIES)

    categories = [signal["category"] for signal in payload["intelligence_signals"]]
    assert categories == intelligence.INTELLIGENCE_CATEGORIES

    for signal in payload["intelligence_signals"]:
        assert signal["status"] == "UNKNOWN"
        assert signal["score"] == 0
        assert signal["confidence"] == 0.0
        assert signal["confidence_level"] == "LOW"
        assert signal["source"] == "deterministic_fallback"
        assert isinstance(signal["risk_flags"], list)
        assert isinstance(signal["recommendations"], list)
        assert isinstance(signal["warnings"], list)


def test_model_sections_are_populated():
    payload = intelligence.build_market_intelligence_report()

    assert payload["score_model"]
    assert payload["confidence_model"]
    assert payload["risk_flag_model"]
    assert payload["recommendation_model"]
    assert payload["integration_targets"]
    assert payload["safety_guarantees"]
    assert payload["limitations"]


def test_report_list_fields_are_lists_with_non_empty_strings_except_signals():
    payload = intelligence.build_market_intelligence_report()

    for field in intelligence.REPORT_LIST_FIELDS:
        assert isinstance(payload[field], list)
        if field == "intelligence_signals":
            continue
        for item in payload[field]:
            assert isinstance(item, str)
            assert item.strip()


def test_signal_list_fields_are_lists_with_non_empty_strings():
    payload = intelligence.build_market_intelligence_report()

    for signal in payload["intelligence_signals"]:
        for field in intelligence.SIGNAL_LIST_FIELDS:
            assert isinstance(signal[field], list)
            for item in signal[field]:
                assert isinstance(item, str)
                assert item.strip()


def test_validate_market_intelligence_report_enforces_paper_only_flags():
    payload = intelligence.build_market_intelligence_report()

    bad_payload = dict(payload)
    bad_payload["paper_trade_mode"] = False
    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)

    bad_payload = dict(payload)
    bad_payload["live_trading_enabled"] = True
    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)

    bad_payload = dict(payload)
    bad_payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_missing_report_required_fields():
    payload = intelligence.build_market_intelligence_report()

    for field in intelligence.REPORT_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_payload.pop(field, None)

        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_missing_signal_required_fields():
    payload = intelligence.build_market_intelligence_report()

    for field in intelligence.SIGNAL_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
        bad_signals[0].pop(field, None)
        bad_payload["intelligence_signals"] = bad_signals

        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_malformed_payload():
    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(None)

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report([])

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report("not-a-payload")


def test_validate_market_intelligence_report_rejects_bad_metadata():
    payload = intelligence.build_market_intelligence_report()

    for field in [
        "bot_name",
        "bot_type",
        "module_name",
        "module_version",
        "schema_version",
        "generated_by",
    ]:
        bad_payload = dict(payload)
        bad_payload[field] = "wrong"

        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_bad_report_list_fields():
    payload = intelligence.build_market_intelligence_report()

    for field in intelligence.REPORT_LIST_FIELDS:
        bad_payload = dict(payload)
        bad_payload[field] = "not-a-list"

        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)

        if field == "intelligence_signals":
            continue

        bad_payload = dict(payload)
        bad_payload[field] = [""]
        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [123]
        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_empty_intelligence_signals():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload["intelligence_signals"] = []

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_bad_signal_list_fields():
    payload = intelligence.build_market_intelligence_report()

    for field in intelligence.SIGNAL_LIST_FIELDS:
        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
        bad_signals[0][field] = "not-a-list"
        bad_payload["intelligence_signals"] = bad_signals
        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)

        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
        bad_signals[0][field] = [""]
        bad_payload["intelligence_signals"] = bad_signals
        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)

        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
        bad_signals[0][field] = [123]
        bad_payload["intelligence_signals"] = bad_signals
        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_supported_status_mismatch():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload["supported_intelligence_statuses"] = list(payload["supported_intelligence_statuses"]) + ["EXTRA"]

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_category_mismatch():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload["intelligence_categories"] = list(payload["intelligence_categories"]) + ["extra_context"]

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_unsupported_overall_status():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload["overall_intelligence_status"] = "NOT_SUPPORTED"

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_unsupported_signal_status():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    bad_signals[0]["status"] = "NOT_SUPPORTED"
    bad_payload["intelligence_signals"] = bad_signals

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_unsupported_signal_category():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    bad_signals[0]["category"] = "unsupported_context"
    bad_payload["intelligence_signals"] = bad_signals

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


def test_validate_market_intelligence_report_rejects_duplicate_signal_category():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    bad_signals[1]["category"] = bad_signals[0]["category"]
    bad_payload["intelligence_signals"] = bad_signals

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("field", ["overall_intelligence_score"])
@pytest.mark.parametrize("bad_value", [-101, 101, "0", True, None])
def test_validate_market_intelligence_report_rejects_bad_overall_score(field, bad_value):
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload[field] = bad_value

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("good_score", [-100, -50.5, 0, 50.5, 100])
def test_validate_market_intelligence_report_accepts_valid_overall_score(good_score):
    payload = intelligence.build_market_intelligence_report()
    good_payload = dict(payload)
    good_payload["overall_intelligence_score"] = good_score

    assert intelligence.validate_market_intelligence_report(good_payload) is True


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, "0.5", True, None])
def test_validate_market_intelligence_report_rejects_bad_overall_confidence(bad_confidence):
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload["overall_confidence"] = bad_confidence

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("good_confidence", [0.0, 0.4, 0.7, 1.0])
def test_validate_market_intelligence_report_accepts_valid_overall_confidence(good_confidence):
    payload = intelligence.build_market_intelligence_report()
    good_payload = dict(payload)
    good_payload["overall_confidence"] = good_confidence

    assert intelligence.validate_market_intelligence_report(good_payload) is True


def test_validate_market_intelligence_report_rejects_bad_overall_confidence_level():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_payload["overall_confidence_level"] = "VERY_HIGH"

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("confidence_level", ["LOW", "MEDIUM", "HIGH"])
def test_validate_market_intelligence_report_accepts_valid_overall_confidence_levels(confidence_level):
    payload = intelligence.build_market_intelligence_report()
    good_payload = dict(payload)
    good_payload["overall_confidence_level"] = confidence_level

    assert intelligence.validate_market_intelligence_report(good_payload) is True


@pytest.mark.parametrize("bad_score", [-101, 101, "0", True, None])
def test_validate_market_intelligence_report_rejects_bad_signal_score(bad_score):
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    bad_signals[0]["score"] = bad_score
    bad_payload["intelligence_signals"] = bad_signals

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("good_score", [-100, -50.5, 0, 50.5, 100])
def test_validate_market_intelligence_report_accepts_valid_signal_score(good_score):
    payload = intelligence.build_market_intelligence_report()
    good_payload = dict(payload)
    good_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    good_signals[0]["score"] = good_score
    good_payload["intelligence_signals"] = good_signals

    assert intelligence.validate_market_intelligence_report(good_payload) is True


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, "0.5", True, None])
def test_validate_market_intelligence_report_rejects_bad_signal_confidence(bad_confidence):
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    bad_signals[0]["confidence"] = bad_confidence
    bad_payload["intelligence_signals"] = bad_signals

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("good_confidence", [0.0, 0.4, 0.7, 1.0])
def test_validate_market_intelligence_report_accepts_valid_signal_confidence(good_confidence):
    payload = intelligence.build_market_intelligence_report()
    good_payload = dict(payload)
    good_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    good_signals[0]["confidence"] = good_confidence
    good_payload["intelligence_signals"] = good_signals

    assert intelligence.validate_market_intelligence_report(good_payload) is True


def test_validate_market_intelligence_report_rejects_bad_signal_confidence_level():
    payload = intelligence.build_market_intelligence_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    bad_signals[0]["confidence_level"] = "VERY_HIGH"
    bad_payload["intelligence_signals"] = bad_signals

    with pytest.raises(ValueError):
        intelligence.validate_market_intelligence_report(bad_payload)


@pytest.mark.parametrize("confidence_level", ["LOW", "MEDIUM", "HIGH"])
def test_validate_market_intelligence_report_accepts_valid_signal_confidence_levels(confidence_level):
    payload = intelligence.build_market_intelligence_report()
    good_payload = dict(payload)
    good_signals = [dict(signal) for signal in payload["intelligence_signals"]]
    good_signals[0]["confidence_level"] = confidence_level
    good_payload["intelligence_signals"] = good_signals

    assert intelligence.validate_market_intelligence_report(good_payload) is True


def test_validate_market_intelligence_report_rejects_bad_signal_source_or_timestamp():
    payload = intelligence.build_market_intelligence_report()

    for field in ["source", "last_updated_utc"]:
        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["intelligence_signals"]]
        bad_signals[0][field] = ""
        bad_payload["intelligence_signals"] = bad_signals

        with pytest.raises(ValueError):
            intelligence.validate_market_intelligence_report(bad_payload)


def test_market_intelligence_report_json_write_read_round_trip(tmp_path):
    output_path = tmp_path / "market_intelligence_report.json"

    written_payload = intelligence.write_market_intelligence_report_json(path=str(output_path))
    read_payload = intelligence.read_market_intelligence_report_json(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert intelligence.validate_market_intelligence_report(read_payload) is True


def test_market_intelligence_report_markdown_generated(tmp_path):
    output_path = tmp_path / "market_intelligence_report.md"

    payload = intelligence.write_market_intelligence_report_markdown(path=str(output_path))
    markdown = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert intelligence.validate_market_intelligence_report(payload) is True
    assert "# Market Intelligence Report" in markdown
    assert "## Overall Intelligence" in markdown
    assert "## Intelligence Signals" in markdown
    assert "UNKNOWN" in markdown
    assert "deterministic_fallback" in markdown


def test_format_market_intelligence_report_markdown_contains_required_sections():
    payload = intelligence.build_market_intelligence_report()

    markdown = intelligence.format_market_intelligence_report_markdown(payload)

    assert "# Market Intelligence Report" in markdown
    assert "## Overall Intelligence" in markdown
    assert "## Intelligence Signals" in markdown
    assert "## Score Model" in markdown
    assert "## Confidence Model" in markdown
    assert "## Risk Flag Model" in markdown
    assert "## Recommendation Model" in markdown
    assert "## Integration Targets" in markdown
    assert "## Safety Guarantees" in markdown
    assert "market_trend" in markdown
    assert "leveraged_etf_risk_context" in markdown
    assert "Overall Intelligence Score" in markdown
    assert "Overall Confidence" in markdown


def test_format_market_intelligence_report_markdown_validates_payload_first():
    payload = intelligence.build_market_intelligence_report()
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        intelligence.format_market_intelligence_report_markdown(payload)


def test_static_safety_no_broker_or_robinhood_imports():
    source = Path(intelligence.__file__).read_text(encoding="utf-8").lower()

    forbidden_import_patterns = [
        "import robinhood",
        "from robinhood",
        "import robin_stocks",
        "from robin_stocks",
        "import broker",
        "from broker",
        "import alpaca",
        "from alpaca",
        "import ibapi",
        "from ibapi",
    ]

    for pattern in forbidden_import_patterns:
        assert pattern not in source


def test_static_safety_no_real_order_placement_logic():
    source = Path(intelligence.__file__).read_text(encoding="utf-8").lower()

    forbidden_runtime_patterns = [
        ".place_order(",
        ".submit_order(",
        ".buy(",
        ".sell(",
        "place_order(",
        "submit_order(",
        "execute_order(",
        "real_order",
        "live_order",
    ]

    for pattern in forbidden_runtime_patterns:
        assert pattern not in source


def test_static_safety_no_subprocess_or_os_system_usage():
    source = Path(intelligence.__file__).read_text(encoding="utf-8")

    forbidden_runtime_patterns = [
        "import subprocess",
        "from subprocess",
        "subprocess.",
        "Popen(",
        "os.system(",
        ".system(",
    ]

    for pattern in forbidden_runtime_patterns:
        assert pattern not in source

    assert "from subprocess import run" not in source


def test_static_safety_no_live_internet_external_api_or_youtube_usage():
    source = Path(intelligence.__file__).read_text(encoding="utf-8").lower()

    forbidden_runtime_patterns = [
        "requests.",
        "urllib.request",
        "http.client",
        "socket.",
        "youtube",
        "googleapiclient",
        "external_api_call",
        "api_key",
        "scrape(",
        "beautifulsoup",
        "selenium",
    ]

    for pattern in forbidden_runtime_patterns:
        assert pattern not in source


def test_static_safety_no_mutation_of_runtime_strategy_files():
    source = Path(intelligence.__file__).read_text(encoding="utf-8")

    forbidden_write_targets = [
        "run_daily_paper_cycle.py",
        "portfolio_engine.py",
        "dividend_engine.py",
        "asset_registry.py",
        "market_regime_engine.py",
    ]

    for target in forbidden_write_targets:
        assert f'open("{target}", "w"' not in source
        assert f"open('{target}', 'w'" not in source
        assert f'Path("{target}").write_text' not in source
        assert f"Path('{target}').write_text" not in source
