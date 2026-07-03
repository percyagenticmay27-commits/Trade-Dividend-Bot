"""
Pytest coverage for market_regime_engine.py.

These tests verify the read-only Market Regime Engine without modifying runtime
workflow files, portfolio logic, dividend logic, asset registry logic, or broker state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import market_regime_engine as regime


def test_module_constants_are_expected():
    assert regime.MODULE_NAME == "market_regime_engine"
    assert regime.MODULE_VERSION == "1.0.0"
    assert regime.SCHEMA_VERSION == "1.0"
    assert regime.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_public_dataclasses_exist():
    assert hasattr(regime, "MarketRegime")
    assert hasattr(regime, "MarketRegimeReport")


def test_required_public_functions_exist_and_are_callable():
    assert callable(regime.build_market_regime_report)
    assert callable(regime.validate_market_regime_report)
    assert callable(regime.write_market_regime_report_json)
    assert callable(regime.read_market_regime_report_json)
    assert callable(regime.format_market_regime_report_markdown)
    assert callable(regime.write_market_regime_report_markdown)


def test_build_market_regime_report_returns_valid_payload():
    payload = regime.build_market_regime_report()

    assert regime.validate_market_regime_report(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["module_name"] == regime.MODULE_NAME
    assert payload["module_version"] == regime.MODULE_VERSION
    assert payload["schema_version"] == regime.SCHEMA_VERSION
    assert payload["generated_by"] == regime.GENERATED_BY


def test_report_required_fields_exist():
    payload = regime.build_market_regime_report()

    for field in regime.REPORT_REQUIRED_FIELDS:
        assert field in payload


def test_market_regime_required_fields_exist():
    payload = regime.build_market_regime_report()
    market_regime = payload["market_regime"]

    for field in regime.MARKET_REGIME_REQUIRED_FIELDS:
        assert field in market_regime


def test_supported_regimes_match_approved_list():
    payload = regime.build_market_regime_report()

    expected = [
        "STRONG_BULL",
        "BULL",
        "NEUTRAL",
        "BEAR",
        "STRONG_BEAR",
        "HIGH_VOLATILITY",
        "UNKNOWN",
    ]

    assert payload["supported_regimes"] == expected
    assert regime.SUPPORTED_REGIMES == expected


def test_default_unknown_fallback_behavior():
    payload = regime.build_market_regime_report()
    market_regime = payload["market_regime"]

    assert market_regime["regime"] == "UNKNOWN"
    assert market_regime["regime_score"] == 0
    assert market_regime["confidence"] == 0.0
    assert market_regime["confidence_level"] == "LOW"
    assert market_regime["portfolio_posture"] == "PAPER_ONLY_OBSERVATION"
    assert market_regime["risk_multiplier"] == 1.0
    assert market_regime["position_sizing_multiplier"] == 1.0
    assert market_regime["cash_reserve_target"] == 0.20


def test_model_sections_are_populated():
    payload = regime.build_market_regime_report()

    assert payload["future_input_sources"]
    assert payload["missing_inputs"] == payload["future_input_sources"]
    assert payload["available_inputs"] == []
    assert payload["scoring_model"]
    assert payload["confidence_model"]
    assert payload["risk_multiplier_model"]
    assert payload["position_sizing_multiplier_model"]
    assert payload["cash_reserve_model"]
    assert payload["integration_targets"]
    assert payload["safety_guarantees"]
    assert payload["limitations"]


def test_report_list_fields_are_lists_with_non_empty_strings():
    payload = regime.build_market_regime_report()

    for field in regime.REPORT_LIST_FIELDS:
        assert isinstance(payload[field], list)
        for item in payload[field]:
            assert isinstance(item, str)
            assert item.strip()


def test_market_regime_list_fields_are_lists_with_non_empty_strings():
    payload = regime.build_market_regime_report()
    market_regime = payload["market_regime"]

    for field in regime.MARKET_REGIME_LIST_FIELDS:
        assert isinstance(market_regime[field], list)
        for item in market_regime[field]:
            assert isinstance(item, str)
            assert item.strip()


def test_validate_market_regime_report_enforces_paper_only_flags():
    payload = regime.build_market_regime_report()

    bad_payload = dict(payload)
    bad_payload["paper_trade_mode"] = False
    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)

    bad_payload = dict(payload)
    bad_payload["live_trading_enabled"] = True
    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)

    bad_payload = dict(payload)
    bad_payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_missing_report_required_fields():
    payload = regime.build_market_regime_report()

    for field in regime.REPORT_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_payload.pop(field, None)

        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_missing_market_regime_required_fields():
    payload = regime.build_market_regime_report()

    for field in regime.MARKET_REGIME_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_market_regime = dict(payload["market_regime"])
        bad_market_regime.pop(field, None)
        bad_payload["market_regime"] = bad_market_regime

        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_malformed_payload():
    with pytest.raises(ValueError):
        regime.validate_market_regime_report(None)

    with pytest.raises(ValueError):
        regime.validate_market_regime_report([])

    with pytest.raises(ValueError):
        regime.validate_market_regime_report("not-a-payload")


def test_validate_market_regime_report_rejects_bad_metadata():
    payload = regime.build_market_regime_report()

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
            regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_bad_report_list_fields():
    payload = regime.build_market_regime_report()

    for field in regime.REPORT_LIST_FIELDS:
        bad_payload = dict(payload)
        bad_payload[field] = "not-a-list"

        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [""]
        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)

        bad_payload = dict(payload)
        bad_payload[field] = [123]
        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_bad_market_regime_list_fields():
    payload = regime.build_market_regime_report()

    for field in regime.MARKET_REGIME_LIST_FIELDS:
        bad_payload = dict(payload)
        bad_market_regime = dict(payload["market_regime"])
        bad_market_regime[field] = "not-a-list"
        bad_payload["market_regime"] = bad_market_regime
        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)

        bad_payload = dict(payload)
        bad_market_regime = dict(payload["market_regime"])
        bad_market_regime[field] = [""]
        bad_payload["market_regime"] = bad_market_regime
        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)

        bad_payload = dict(payload)
        bad_market_regime = dict(payload["market_regime"])
        bad_market_regime[field] = [123]
        bad_payload["market_regime"] = bad_market_regime
        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_supported_regime_mismatch():
    payload = regime.build_market_regime_report()
    bad_payload = dict(payload)
    bad_payload["supported_regimes"] = list(payload["supported_regimes"]) + ["EXTRA"]

    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


def test_validate_market_regime_report_rejects_unsupported_market_regime():
    payload = regime.build_market_regime_report()
    bad_payload = dict(payload)
    bad_market_regime = dict(payload["market_regime"])
    bad_market_regime["regime"] = "NOT_SUPPORTED"
    bad_payload["market_regime"] = bad_market_regime

    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


@pytest.mark.parametrize("bad_score", [-101, 101, "0", True, None])
def test_validate_market_regime_report_rejects_bad_regime_score(bad_score):
    payload = regime.build_market_regime_report()
    bad_payload = dict(payload)
    bad_market_regime = dict(payload["market_regime"])
    bad_market_regime["regime_score"] = bad_score
    bad_payload["market_regime"] = bad_market_regime

    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


@pytest.mark.parametrize("good_score", [-100, -50.5, 0, 50.5, 100])
def test_validate_market_regime_report_accepts_valid_regime_score(good_score):
    payload = regime.build_market_regime_report()
    good_payload = dict(payload)
    good_market_regime = dict(payload["market_regime"])
    good_market_regime["regime_score"] = good_score
    good_payload["market_regime"] = good_market_regime

    assert regime.validate_market_regime_report(good_payload) is True


@pytest.mark.parametrize("bad_confidence", [-0.01, 1.01, "0.5", True, None])
def test_validate_market_regime_report_rejects_bad_confidence(bad_confidence):
    payload = regime.build_market_regime_report()
    bad_payload = dict(payload)
    bad_market_regime = dict(payload["market_regime"])
    bad_market_regime["confidence"] = bad_confidence
    bad_payload["market_regime"] = bad_market_regime

    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


@pytest.mark.parametrize("good_confidence", [0.0, 0.4, 0.7, 1.0])
def test_validate_market_regime_report_accepts_valid_confidence(good_confidence):
    payload = regime.build_market_regime_report()
    good_payload = dict(payload)
    good_market_regime = dict(payload["market_regime"])
    good_market_regime["confidence"] = good_confidence
    good_payload["market_regime"] = good_market_regime

    assert regime.validate_market_regime_report(good_payload) is True


def test_validate_market_regime_report_rejects_bad_confidence_level():
    payload = regime.build_market_regime_report()
    bad_payload = dict(payload)
    bad_market_regime = dict(payload["market_regime"])
    bad_market_regime["confidence_level"] = "VERY_HIGH"
    bad_payload["market_regime"] = bad_market_regime

    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


@pytest.mark.parametrize("confidence_level", ["LOW", "MEDIUM", "HIGH"])
def test_validate_market_regime_report_accepts_valid_confidence_levels(confidence_level):
    payload = regime.build_market_regime_report()
    good_payload = dict(payload)
    good_market_regime = dict(payload["market_regime"])
    good_market_regime["confidence_level"] = confidence_level
    good_payload["market_regime"] = good_market_regime

    assert regime.validate_market_regime_report(good_payload) is True


@pytest.mark.parametrize("field,minimum,maximum", [
    ("risk_multiplier", 0.25, 1.50),
    ("position_sizing_multiplier", 0.25, 1.25),
    ("cash_reserve_target", 0.0, 1.0),
])
def test_validate_market_regime_report_rejects_numeric_ranges(field, minimum, maximum):
    payload = regime.build_market_regime_report()

    for bad_value in [minimum - 0.01, maximum + 0.01, "1", True, None]:
        bad_payload = dict(payload)
        bad_market_regime = dict(payload["market_regime"])
        bad_market_regime[field] = bad_value
        bad_payload["market_regime"] = bad_market_regime

        with pytest.raises(ValueError):
            regime.validate_market_regime_report(bad_payload)


@pytest.mark.parametrize("field,valid_values", [
    ("risk_multiplier", [0.25, 1.0, 1.50]),
    ("position_sizing_multiplier", [0.25, 1.0, 1.25]),
    ("cash_reserve_target", [0.0, 0.20, 1.0]),
])
def test_validate_market_regime_report_accepts_numeric_ranges(field, valid_values):
    payload = regime.build_market_regime_report()

    for value in valid_values:
        good_payload = dict(payload)
        good_market_regime = dict(payload["market_regime"])
        good_market_regime[field] = value
        good_payload["market_regime"] = good_market_regime

        assert regime.validate_market_regime_report(good_payload) is True


def test_validate_market_regime_report_rejects_empty_portfolio_posture():
    payload = regime.build_market_regime_report()
    bad_payload = dict(payload)
    bad_market_regime = dict(payload["market_regime"])
    bad_market_regime["portfolio_posture"] = ""
    bad_payload["market_regime"] = bad_market_regime

    with pytest.raises(ValueError):
        regime.validate_market_regime_report(bad_payload)


def test_market_regime_report_json_write_read_round_trip(tmp_path):
    output_path = tmp_path / "market_regime_report.json"

    written_payload = regime.write_market_regime_report_json(path=str(output_path))
    read_payload = regime.read_market_regime_report_json(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert regime.validate_market_regime_report(read_payload) is True


def test_market_regime_report_markdown_generated(tmp_path):
    output_path = tmp_path / "market_regime_report.md"

    payload = regime.write_market_regime_report_markdown(path=str(output_path))
    markdown = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert regime.validate_market_regime_report(payload) is True
    assert "# Market Regime Report" in markdown
    assert "UNKNOWN" in markdown
    assert "PAPER_ONLY_OBSERVATION" in markdown


def test_format_market_regime_report_markdown_contains_required_sections():
    payload = regime.build_market_regime_report()

    markdown = regime.format_market_regime_report_markdown(payload)

    assert "# Market Regime Report" in markdown
    assert "## Current Regime" in markdown
    assert "## Supported Regimes" in markdown
    assert "## Scoring Model" in markdown
    assert "## Confidence Model" in markdown
    assert "## Risk Multiplier Model" in markdown
    assert "## Position Sizing Multiplier Model" in markdown
    assert "## Cash Reserve Model" in markdown
    assert "## Integration Targets" in markdown
    assert "## Safety Guarantees" in markdown
    assert "Regime Score" in markdown
    assert "Confidence" in markdown
    assert "Risk Multiplier" in markdown
    assert "Cash Reserve Target" in markdown


def test_format_market_regime_report_markdown_validates_payload_first():
    payload = regime.build_market_regime_report()
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        regime.format_market_regime_report_markdown(payload)


def test_static_safety_no_broker_or_robinhood_imports():
    source = Path(regime.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(regime.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(regime.__file__).read_text(encoding="utf-8")

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


def test_static_safety_no_mutation_of_runtime_strategy_files():
    source = Path(regime.__file__).read_text(encoding="utf-8")

    forbidden_write_targets = [
        "run_daily_paper_cycle.py",
        "portfolio_engine.py",
        "dividend_engine.py",
        "asset_registry.py",
    ]

    for target in forbidden_write_targets:
        assert f'open("{target}", "w"' not in source
        assert f"open('{target}', 'w'" not in source
        assert f'Path("{target}").write_text' not in source
        assert f"Path('{target}').write_text" not in source
