"""
Pytest coverage for momentum_score_engine.py.

These tests verify the read-only Momentum Score Engine without modifying runtime
workflow files, portfolio logic, dividend logic, asset registry logic, market
regime logic, market intelligence logic, or broker state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import momentum_score_engine as momentum


def test_module_constants_are_expected():
    assert momentum.MODULE_NAME == "momentum_score_engine"
    assert momentum.MODULE_VERSION == "1.0.0"
    assert momentum.SCHEMA_VERSION == "1.0"
    assert momentum.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_public_dataclasses_exist():
    assert hasattr(momentum, "MomentumSignal")
    assert hasattr(momentum, "MomentumScoreReport")


def test_required_public_functions_exist_and_are_callable():
    assert callable(momentum.build_momentum_score_report)
    assert callable(momentum.validate_momentum_score_report)
    assert callable(momentum.write_momentum_score_report_json)
    assert callable(momentum.read_momentum_score_report_json)
    assert callable(momentum.format_momentum_score_report_markdown)
    assert callable(momentum.write_momentum_score_report_markdown)


def test_build_momentum_score_report_returns_valid_payload():
    payload = momentum.build_momentum_score_report()

    assert momentum.validate_momentum_score_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["module_name"] == momentum.MODULE_NAME
    assert payload["module_version"] == momentum.MODULE_VERSION
    assert payload["schema_version"] == momentum.SCHEMA_VERSION
    assert payload["generated_by"] == momentum.GENERATED_BY


def test_report_required_fields_exist():
    payload = momentum.build_momentum_score_report()

    for field in momentum.REPORT_REQUIRED_FIELDS:
        assert field in payload


def test_signal_required_fields_exist():
    payload = momentum.build_momentum_score_report()

    for signal in payload["momentum_signals"]:
        for field in momentum.SIGNAL_REQUIRED_FIELDS:
            assert field in signal


def test_supported_momentum_statuses_match_approved_list():
    payload = momentum.build_momentum_score_report()

    expected = ["STRONG", "MODERATE", "WEAK", "NEGATIVE", "MIXED", "UNKNOWN"]

    assert payload["supported_momentum_statuses"] == expected
    assert momentum.SUPPORTED_MOMENTUM_STATUSES == expected


def test_supported_trend_directions_match_approved_list():
    payload = momentum.build_momentum_score_report()

    expected = ["UP", "DOWN", "SIDEWAYS", "REVERSAL_UP", "REVERSAL_DOWN", "UNKNOWN"]

    assert payload["supported_trend_directions"] == expected
    assert momentum.SUPPORTED_TREND_DIRECTIONS == expected


def test_momentum_signal_names_match_approved_list():
    payload = momentum.build_momentum_score_report()

    expected = [
        "price_trend",
        "relative_strength",
        "moving_average_alignment",
        "volume_confirmation",
        "breakout_confirmation",
        "pullback_quality",
        "trend_consistency",
        "volatility_adjusted_momentum",
        "sector_relative_strength",
        "market_regime_confirmation",
        "market_intelligence_confirmation",
    ]

    assert payload["momentum_signal_names"] == expected
    assert momentum.MOMENTUM_SIGNAL_NAMES == expected


def test_default_overall_behavior():
    payload = momentum.build_momentum_score_report()

    assert payload["momentum_score"] == 0
    assert payload["momentum_status"] == "UNKNOWN"
    assert payload["confidence"] == 0.0
    assert payload["confidence_level"] == "LOW"
    assert payload["trend_direction"] == "UNKNOWN"


def test_default_signal_behavior():
    payload = momentum.build_momentum_score_report()

    assert len(payload["momentum_signals"]) == len(momentum.MOMENTUM_SIGNAL_NAMES)

    signal_names = [signal["signal_name"] for signal in payload["momentum_signals"]]
    assert signal_names == momentum.MOMENTUM_SIGNAL_NAMES

    for signal in payload["momentum_signals"]:
        assert signal["score"] == 0
        assert signal["status"] == "UNKNOWN"
        assert signal["confidence"] == 0.0
        assert signal["confidence_level"] == "LOW"
        assert signal["trend_direction"] == "UNKNOWN"
        assert signal["source"] == "deterministic_fallback"
        assert isinstance(signal["risk_flags"], list)
        assert isinstance(signal["recommendations"], list)
        assert isinstance(signal["warnings"], list)


def test_model_sections_are_populated():
    payload = momentum.build_momentum_score_report()

    assert payload["scoring_model"]
    assert payload["signal_weight_model"]
    assert payload["momentum_quality_model"]
    assert payload["confidence_model"]
    assert payload["trend_direction_model"]
    assert payload["risk_flag_model"]
    assert payload["recommendation_model"]
    assert payload["integration_targets"]
    assert payload["safety_guarantees"]
    assert payload["limitations"]


def test_report_list_fields_are_lists_with_non_empty_strings_except_signals():
    payload = momentum.build_momentum_score_report()

    for field in momentum.REPORT_LIST_FIELDS:
        assert isinstance(payload[field], list)
        if field == "momentum_signals":
            continue
        for item in payload[field]:
            assert isinstance(item, str)
            assert item.strip()


def test_signal_list_fields_are_lists_with_non_empty_strings():
    payload = momentum.build_momentum_score_report()

    for signal in payload["momentum_signals"]:
        for field in momentum.SIGNAL_LIST_FIELDS:
            assert isinstance(signal[field], list)
            for item in signal[field]:
                assert isinstance(item, str)
                assert item.strip()


def test_validate_momentum_score_report_enforces_paper_only_flags():
    payload = momentum.build_momentum_score_report()

    bad_payload = dict(payload)
    bad_payload["paper_trade_mode"] = False
    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)

    bad_payload = dict(payload)
    bad_payload["live_trading_enabled"] = True
    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)

    bad_payload = dict(payload)
    bad_payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_missing_report_required_fields():
    payload = momentum.build_momentum_score_report()

    for field in momentum.REPORT_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_payload.pop(field, None)

        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_missing_signal_required_fields():
    payload = momentum.build_momentum_score_report()

    for field in momentum.SIGNAL_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
        bad_signals[0].pop(field, None)
        bad_payload["momentum_signals"] = bad_signals

        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_malformed_payload():
    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(None)

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report([])

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report("not-a-payload")


def test_validate_momentum_score_report_rejects_bad_metadata():
    payload = momentum.build_momentum_score_report()

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
            momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_bad_report_list_fields():
    payload = momentum.build_momentum_score_report()

    for field in momentum.REPORT_LIST_FIELDS:
        bad_payload = dict(payload)
        bad_payload[field] = "not-a-list"

        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)

        if field == "momentum_signals":
            continue

        bad_payload = dict(payload)
        bad_payload[field] = [""]
        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [123]
        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_empty_momentum_signals():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["momentum_signals"] = []

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_bad_signal_list_fields():
    payload = momentum.build_momentum_score_report()

    for field in momentum.SIGNAL_LIST_FIELDS:
        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
        bad_signals[0][field] = "not-a-list"
        bad_payload["momentum_signals"] = bad_signals
        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)

        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
        bad_signals[0][field] = [""]
        bad_payload["momentum_signals"] = bad_signals
        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)

        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
        bad_signals[0][field] = [123]
        bad_payload["momentum_signals"] = bad_signals
        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_supported_status_mismatch():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["supported_momentum_statuses"] = list(payload["supported_momentum_statuses"]) + ["EXTRA"]

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_trend_direction_mismatch():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["supported_trend_directions"] = list(payload["supported_trend_directions"]) + ["EXTRA"]

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_signal_name_mismatch():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["momentum_signal_names"] = list(payload["momentum_signal_names"]) + ["extra_signal"]

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_unsupported_overall_status():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["momentum_status"] = "NOT_SUPPORTED"

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_unsupported_overall_trend_direction():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["trend_direction"] = "NOT_SUPPORTED"

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_unsupported_signal_status():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[0]["status"] = "NOT_SUPPORTED"
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_unsupported_signal_name():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[0]["signal_name"] = "unsupported_signal"
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_unsupported_signal_trend_direction():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[0]["trend_direction"] = "NOT_SUPPORTED"
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


def test_validate_momentum_score_report_rejects_duplicate_signal_name():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[1]["signal_name"] = bad_signals[0]["signal_name"]
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("bad_score", [-1, 101, "0", True, None])
def test_validate_momentum_score_report_rejects_bad_overall_score(bad_score):
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["momentum_score"] = bad_score

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("good_score", [0, 25.5, 50, 75.5, 100])
def test_validate_momentum_score_report_accepts_valid_overall_score(good_score):
    payload = momentum.build_momentum_score_report()
    good_payload = dict(payload)
    good_payload["momentum_score"] = good_score

    assert momentum.validate_momentum_score_report(good_payload) is True


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, "0.5", True, None])
def test_validate_momentum_score_report_rejects_bad_overall_confidence(bad_confidence):
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["confidence"] = bad_confidence

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("good_confidence", [0.0, 0.4, 0.7, 1.0])
def test_validate_momentum_score_report_accepts_valid_overall_confidence(good_confidence):
    payload = momentum.build_momentum_score_report()
    good_payload = dict(payload)
    good_payload["confidence"] = good_confidence

    assert momentum.validate_momentum_score_report(good_payload) is True


def test_validate_momentum_score_report_rejects_bad_overall_confidence_level():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_payload["confidence_level"] = "VERY_HIGH"

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("confidence_level", ["LOW", "MEDIUM", "HIGH"])
def test_validate_momentum_score_report_accepts_valid_overall_confidence_levels(confidence_level):
    payload = momentum.build_momentum_score_report()
    good_payload = dict(payload)
    good_payload["confidence_level"] = confidence_level

    assert momentum.validate_momentum_score_report(good_payload) is True


@pytest.mark.parametrize("bad_score", [-1, 101, "0", True, None])
def test_validate_momentum_score_report_rejects_bad_signal_score(bad_score):
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[0]["score"] = bad_score
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("good_score", [0, 25.5, 50, 75.5, 100])
def test_validate_momentum_score_report_accepts_valid_signal_score(good_score):
    payload = momentum.build_momentum_score_report()
    good_payload = dict(payload)
    good_signals = [dict(signal) for signal in payload["momentum_signals"]]
    good_signals[0]["score"] = good_score
    good_payload["momentum_signals"] = good_signals

    assert momentum.validate_momentum_score_report(good_payload) is True


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, "0.5", True, None])
def test_validate_momentum_score_report_rejects_bad_signal_confidence(bad_confidence):
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[0]["confidence"] = bad_confidence
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("good_confidence", [0.0, 0.4, 0.7, 1.0])
def test_validate_momentum_score_report_accepts_valid_signal_confidence(good_confidence):
    payload = momentum.build_momentum_score_report()
    good_payload = dict(payload)
    good_signals = [dict(signal) for signal in payload["momentum_signals"]]
    good_signals[0]["confidence"] = good_confidence
    good_payload["momentum_signals"] = good_signals

    assert momentum.validate_momentum_score_report(good_payload) is True


def test_validate_momentum_score_report_rejects_bad_signal_confidence_level():
    payload = momentum.build_momentum_score_report()
    bad_payload = dict(payload)
    bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
    bad_signals[0]["confidence_level"] = "VERY_HIGH"
    bad_payload["momentum_signals"] = bad_signals

    with pytest.raises(ValueError):
        momentum.validate_momentum_score_report(bad_payload)


@pytest.mark.parametrize("confidence_level", ["LOW", "MEDIUM", "HIGH"])
def test_validate_momentum_score_report_accepts_valid_signal_confidence_levels(confidence_level):
    payload = momentum.build_momentum_score_report()
    good_payload = dict(payload)
    good_signals = [dict(signal) for signal in payload["momentum_signals"]]
    good_signals[0]["confidence_level"] = confidence_level
    good_payload["momentum_signals"] = good_signals

    assert momentum.validate_momentum_score_report(good_payload) is True


def test_validate_momentum_score_report_rejects_bad_signal_source_or_timestamp():
    payload = momentum.build_momentum_score_report()

    for field in ["source", "last_updated_utc"]:
        bad_payload = dict(payload)
        bad_signals = [dict(signal) for signal in payload["momentum_signals"]]
        bad_signals[0][field] = ""
        bad_payload["momentum_signals"] = bad_signals

        with pytest.raises(ValueError):
            momentum.validate_momentum_score_report(bad_payload)


def test_momentum_score_report_json_write_read_round_trip(tmp_path):
    output_path = tmp_path / "momentum_score_report.json"

    written_payload = momentum.write_momentum_score_report_json(path=str(output_path))
    read_payload = momentum.read_momentum_score_report_json(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert momentum.validate_momentum_score_report(read_payload) is True


def test_momentum_score_report_markdown_generated(tmp_path):
    output_path = tmp_path / "momentum_score_report.md"

    payload = momentum.write_momentum_score_report_markdown(path=str(output_path))
    markdown = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert momentum.validate_momentum_score_report(payload) is True
    assert "# Momentum Score Report" in markdown
    assert "## Overall Momentum" in markdown
    assert "## Momentum Signals" in markdown
    assert "UNKNOWN" in markdown
    assert "deterministic_fallback" in markdown


def test_format_momentum_score_report_markdown_contains_required_sections():
    payload = momentum.build_momentum_score_report()

    markdown = momentum.format_momentum_score_report_markdown(payload)

    assert "# Momentum Score Report" in markdown
    assert "## Overall Momentum" in markdown
    assert "## Momentum Signals" in markdown
    assert "## Scoring Model" in markdown
    assert "## Signal Weight Model" in markdown
    assert "## Momentum Quality Model" in markdown
    assert "## Confidence Model" in markdown
    assert "## Trend Direction Model" in markdown
    assert "## Integration Targets" in markdown
    assert "## Safety Guarantees" in markdown
    assert "price_trend" in markdown
    assert "market_intelligence_confirmation" in markdown
    assert "Momentum Score" in markdown
    assert "Trend Direction" in markdown


def test_format_momentum_score_report_markdown_validates_payload_first():
    payload = momentum.build_momentum_score_report()
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        momentum.format_momentum_score_report_markdown(payload)


def test_static_safety_no_broker_or_robinhood_imports():
    source = Path(momentum.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(momentum.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(momentum.__file__).read_text(encoding="utf-8")

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


def test_static_safety_no_live_internet_or_external_api_usage():
    source = Path(momentum.__file__).read_text(encoding="utf-8").lower()

    forbidden_runtime_patterns = [
        "requests.",
        "urllib.request",
        "http.client",
        "socket.",
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
    source = Path(momentum.__file__).read_text(encoding="utf-8")

    forbidden_write_targets = [
        "run_daily_paper_cycle.py",
        "portfolio_engine.py",
        "dividend_engine.py",
        "asset_registry.py",
        "market_regime_engine.py",
        "market_intelligence_engine.py",
    ]

    for target in forbidden_write_targets:
        assert f'open("{target}", "w"' not in source
        assert f"open('{target}', 'w'" not in source
        assert f'Path("{target}").write_text' not in source
        assert f"Path('{target}').write_text" not in source
