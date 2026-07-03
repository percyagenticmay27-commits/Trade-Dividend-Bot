"""
Pytest coverage for asset_registry.py.

These tests verify the read-only Asset Registry & Classification Engine without
modifying runtime workflow files, portfolio logic, dividend logic, or broker state.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import asset_registry as registry


def _mapping_by_symbol(payload: dict, symbol: str) -> dict:
    for mapping in payload["asset_mappings"]:
        if mapping["symbol"] == symbol:
            return mapping
    raise AssertionError(f"Missing mapping for {symbol}")


def test_module_constants_are_expected():
    assert registry.MODULE_NAME == "asset_registry"
    assert registry.MODULE_VERSION == "1.0.0"
    assert registry.SCHEMA_VERSION == "1.0"
    assert registry.GENERATED_BY == "Agentic-Robin-Dividend.bot"


def test_public_dataclasses_exist():
    assert hasattr(registry, "AssetMapping")
    assert hasattr(registry, "AssetRegistryPayload")


def test_required_public_functions_exist_and_are_callable():
    assert callable(registry.build_asset_registry)
    assert callable(registry.validate_asset_registry)
    assert callable(registry.write_asset_registry_json)
    assert callable(registry.read_asset_registry_json)
    assert callable(registry.format_asset_registry_markdown)
    assert callable(registry.write_asset_registry_markdown)
    assert callable(registry.get_asset_mapping)
    assert callable(registry.get_preferred_vehicle)
    assert callable(registry.get_candidate_vehicles)
    assert callable(registry.classify_asset)
    assert callable(registry.is_promotion_eligible)
    assert callable(registry.get_strategy_pipeline)


def test_build_asset_registry_returns_valid_payload():
    payload = registry.build_asset_registry()

    assert registry.validate_asset_registry(payload) is True
    assert payload["paper_trade_mode"] is True
    assert payload["live_trading_enabled"] is False
    assert payload["broker_execution_enabled"] is False
    assert payload["module_name"] == registry.MODULE_NAME
    assert payload["module_version"] == registry.MODULE_VERSION
    assert payload["schema_version"] == registry.SCHEMA_VERSION
    assert payload["generated_by"] == registry.GENERATED_BY


def test_supported_classifications_are_complete():
    payload = registry.build_asset_registry()

    expected = [
        "UNDERLYING_EQUITY",
        "LEVERAGED_ETF",
        "INCOME_ETF",
        "OPTION_STRATEGY_ETF",
        "SECTOR_ETF",
        "THEMATIC_ETF",
        "BROAD_MARKET_ETF",
        "CRYPTO_ETF",
        "COMMODITY_ETF",
        "SPECIALTY_ETF",
        "UNKNOWN",
    ]

    assert payload["supported_classifications"] == expected


def test_initial_primary_mappings_are_present_and_correct():
    payload = registry.build_asset_registry()

    aapl = _mapping_by_symbol(payload, "AAPL")
    googl = _mapping_by_symbol(payload, "GOOGL")
    nbis = _mapping_by_symbol(payload, "NBIS")
    qqq = _mapping_by_symbol(payload, "QQQ")

    assert aapl["preferred_symbol"] == "AAPU"
    assert aapl["fallback_symbol"] == "AAPL"
    assert aapl["classification"] == "UNDERLYING_EQUITY"
    assert aapl["preferred_vehicle_classification"] == "LEVERAGED_ETF"
    assert aapl["candidate_symbols"] == ["AAPU", "AAPL"]
    assert aapl["leverage"] == "2x"
    assert aapl["strategy_pipeline"] == "leveraged_equity_vehicle_pipeline"

    assert googl["preferred_symbol"] == "GGLL"
    assert googl["fallback_symbol"] == "GOOGL"
    assert googl["classification"] == "UNDERLYING_EQUITY"
    assert googl["preferred_vehicle_classification"] == "LEVERAGED_ETF"
    assert googl["candidate_symbols"] == ["GGLL", "GOOGL"]
    assert googl["leverage"] == "2x"
    assert googl["strategy_pipeline"] == "leveraged_equity_vehicle_pipeline"

    assert nbis["preferred_symbol"] == "NEBX"
    assert nbis["fallback_symbol"] == "NBIS"
    assert nbis["classification"] == "UNDERLYING_EQUITY"
    assert nbis["preferred_vehicle_classification"] == "LEVERAGED_ETF"
    assert nbis["candidate_symbols"] == ["NEBX", "NBIS"]
    assert nbis["leverage"] == "2x"
    assert nbis["strategy_pipeline"] == "leveraged_equity_vehicle_pipeline"

    assert qqq["preferred_symbol"] == "TQQQ"
    assert qqq["fallback_symbol"] == "QQQ"
    assert qqq["classification"] == "BROAD_MARKET_ETF"
    assert qqq["preferred_vehicle_classification"] == "LEVERAGED_ETF"
    assert qqq["candidate_symbols"] == ["TQQQ", "QQQ"]
    assert qqq["leverage"] == "3x"
    assert qqq["strategy_pipeline"] == "leveraged_index_etf_pipeline"


def test_one_to_many_candidate_mapping_support():
    payload = registry.build_asset_registry()

    for symbol in ["AAPL", "GOOGL", "NBIS", "QQQ"]:
        mapping = _mapping_by_symbol(payload, symbol)
        assert isinstance(mapping["candidate_symbols"], list)
        assert len(mapping["candidate_symbols"]) >= 2
        assert mapping["preferred_symbol"] in mapping["candidate_symbols"]
        assert mapping["fallback_symbol"] in mapping["candidate_symbols"]


def test_lookup_helpers_for_primary_symbols():
    assert registry.get_asset_mapping("AAPL")["symbol"] == "AAPL"
    assert registry.get_preferred_vehicle("AAPL") == "AAPU"
    assert registry.get_preferred_vehicle("GOOGL") == "GGLL"
    assert registry.get_preferred_vehicle("NBIS") == "NEBX"
    assert registry.get_preferred_vehicle("QQQ") == "TQQQ"

    assert registry.get_candidate_vehicles("AAPL") == ["AAPU", "AAPL"]
    assert registry.get_candidate_vehicles("GOOGL") == ["GGLL", "GOOGL"]
    assert registry.get_candidate_vehicles("NBIS") == ["NEBX", "NBIS"]
    assert registry.get_candidate_vehicles("QQQ") == ["TQQQ", "QQQ"]

    assert registry.classify_asset("AAPL") == "UNDERLYING_EQUITY"
    assert registry.classify_asset("GOOGL") == "UNDERLYING_EQUITY"
    assert registry.classify_asset("NBIS") == "UNDERLYING_EQUITY"
    assert registry.classify_asset("QQQ") == "BROAD_MARKET_ETF"

    assert registry.is_promotion_eligible("AAPL") is True
    assert registry.get_strategy_pipeline("AAPL") == "leveraged_equity_vehicle_pipeline"
    assert registry.get_strategy_pipeline("QQQ") == "leveraged_index_etf_pipeline"


def test_lookup_helpers_for_preferred_vehicle_symbols():
    assert registry.get_asset_mapping("AAPU")["symbol"] == "AAPL"
    assert registry.get_asset_mapping("GGLL")["symbol"] == "GOOGL"
    assert registry.get_asset_mapping("NEBX")["symbol"] == "NBIS"
    assert registry.get_asset_mapping("TQQQ")["symbol"] == "QQQ"

    assert registry.classify_asset("AAPU") == "LEVERAGED_ETF"
    assert registry.classify_asset("GGLL") == "LEVERAGED_ETF"
    assert registry.classify_asset("NEBX") == "LEVERAGED_ETF"
    assert registry.classify_asset("TQQQ") == "LEVERAGED_ETF"

    assert registry.get_preferred_vehicle("AAPU") == "AAPU"
    assert registry.get_preferred_vehicle("GGLL") == "GGLL"
    assert registry.get_preferred_vehicle("NEBX") == "NEBX"
    assert registry.get_preferred_vehicle("TQQQ") == "TQQQ"


def test_unknown_symbol_behavior():
    assert registry.get_asset_mapping("XYZUNKNOWN") is None
    assert registry.get_preferred_vehicle("XYZUNKNOWN") is None
    assert registry.get_candidate_vehicles("XYZUNKNOWN") == []
    assert registry.classify_asset("XYZUNKNOWN") == "UNKNOWN"
    assert registry.is_promotion_eligible("XYZUNKNOWN") is False
    assert registry.get_strategy_pipeline("XYZUNKNOWN") == "manual_review_pipeline"


def test_lookup_helpers_normalize_lowercase_input():
    assert registry.get_preferred_vehicle("aapl") == "AAPU"
    assert registry.classify_asset("aapu") == "LEVERAGED_ETF"
    assert registry.get_strategy_pipeline("qqq") == "leveraged_index_etf_pipeline"


def test_lookup_helpers_reject_blank_or_invalid_symbol():
    for bad_symbol in ["", "   ", None]:
        with pytest.raises(ValueError):
            registry.get_asset_mapping(bad_symbol)


def test_validate_asset_registry_enforces_paper_only_flags():
    payload = registry.build_asset_registry()

    bad_payload = dict(payload)
    bad_payload["paper_trade_mode"] = False
    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)

    bad_payload = dict(payload)
    bad_payload["live_trading_enabled"] = True
    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)

    bad_payload = dict(payload)
    bad_payload["broker_execution_enabled"] = True
    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_enforces_mapping_paper_only_flags():
    payload = registry.build_asset_registry()

    for field, value in [
        ("paper_trade_mode", False),
        ("live_trading_enabled", True),
        ("broker_execution_enabled", True),
    ]:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0][field] = value
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_missing_registry_required_fields():
    payload = registry.build_asset_registry()

    for field in registry.REGISTRY_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_payload.pop(field, None)

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_missing_mapping_required_fields():
    payload = registry.build_asset_registry()

    for field in registry.ASSET_MAPPING_REQUIRED_FIELDS:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0].pop(field, None)
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_malformed_payload():
    with pytest.raises(ValueError):
        registry.validate_asset_registry(None)

    with pytest.raises(ValueError):
        registry.validate_asset_registry([])

    with pytest.raises(ValueError):
        registry.validate_asset_registry("not-a-payload")


def test_validate_asset_registry_rejects_bad_metadata():
    payload = registry.build_asset_registry()

    for field in [
        "registry_name",
        "bot_name",
        "bot_type",
        "registry_version",
        "schema_version",
        "generated_by",
        "module_name",
        "module_version",
    ]:
        bad_payload = dict(payload)
        bad_payload[field] = "wrong"

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_bad_list_fields():
    payload = registry.build_asset_registry()

    for field in registry.LIST_FIELDS:
        bad_payload = dict(payload)
        bad_payload[field] = "not-a-list"

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_empty_asset_mappings():
    payload = registry.build_asset_registry()
    bad_payload = dict(payload)
    bad_payload["asset_mappings"] = []

    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_bad_symbols():
    payload = registry.build_asset_registry()

    for field in ["symbol", "preferred_symbol", "fallback_symbol"]:
        for bad_value in ["", "   ", "aapl", "AAPL ", 123]:
            bad_payload = dict(payload)
            bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
            bad_mappings[0][field] = bad_value
            bad_payload["asset_mappings"] = bad_mappings

            with pytest.raises(ValueError):
                registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_unsupported_classifications():
    payload = registry.build_asset_registry()

    for field in ["classification", "preferred_vehicle_classification"]:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0][field] = "NOT_SUPPORTED"
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_bad_candidate_symbols():
    payload = registry.build_asset_registry()

    bad_values = [
        [],
        "AAPU",
        ["AAPU", ""],
        ["AAPU", "aapl"],
        ["AAPU", "AAPL "],
        ["AAPU", 123],
    ]

    for bad_value in bad_values:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0]["candidate_symbols"] = bad_value
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_requires_preferred_symbol_in_candidates():
    payload = registry.build_asset_registry()
    bad_payload = dict(payload)
    bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
    bad_mappings[0]["candidate_symbols"] = ["AAPL"]
    bad_payload["asset_mappings"] = bad_mappings

    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_requires_fallback_symbol_in_candidates():
    payload = registry.build_asset_registry()
    bad_payload = dict(payload)
    bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
    bad_mappings[0]["candidate_symbols"] = ["AAPU"]
    bad_payload["asset_mappings"] = bad_mappings

    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_bad_leverage():
    payload = registry.build_asset_registry()

    for bad_value in ["4x", "2X", "", 2]:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0]["leverage"] = bad_value
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_accepts_allowed_leverage_values():
    payload = registry.build_asset_registry()

    for allowed_value in ["1x", "2x", "3x", None]:
        good_payload = dict(payload)
        good_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        good_mappings[0]["leverage"] = allowed_value
        good_payload["asset_mappings"] = good_mappings

        assert registry.validate_asset_registry(good_payload) is True


def test_validate_asset_registry_rejects_duplicate_primary_symbols():
    payload = registry.build_asset_registry()
    bad_payload = dict(payload)
    bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
    duplicate = dict(bad_mappings[0])
    bad_mappings.append(duplicate)
    bad_payload["asset_mappings"] = bad_mappings

    with pytest.raises(ValueError):
        registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_bad_promotion_fields():
    payload = registry.build_asset_registry()

    for field in ["promotion_eligible", "requires_manual_review", "preferred_for_paper_strategy"]:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0][field] = "yes"
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_validate_asset_registry_rejects_bad_strategy_and_promotion_text_fields():
    payload = registry.build_asset_registry()

    for field in ["strategy_pipeline", "promotion_reason", "risk_class"]:
        bad_payload = dict(payload)
        bad_mappings = [dict(mapping) for mapping in payload["asset_mappings"]]
        bad_mappings[0][field] = ""
        bad_payload["asset_mappings"] = bad_mappings

        with pytest.raises(ValueError):
            registry.validate_asset_registry(bad_payload)


def test_asset_registry_json_write_read_round_trip(tmp_path):
    output_path = tmp_path / "asset_registry.json"

    written_payload = registry.write_asset_registry_json(path=str(output_path))
    read_payload = registry.read_asset_registry_json(path=str(output_path))

    assert output_path.exists()
    assert read_payload == written_payload
    assert registry.validate_asset_registry(read_payload) is True


def test_asset_registry_markdown_generated(tmp_path):
    output_path = tmp_path / "asset_registry.md"

    payload = registry.write_asset_registry_markdown(path=str(output_path))
    markdown = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert registry.validate_asset_registry(payload) is True
    assert "# Dividend Bot Asset Registry" in markdown
    assert "## Asset Mappings" in markdown
    assert "AAPL" in markdown
    assert "AAPU" in markdown
    assert "GOOGL" in markdown
    assert "GGLL" in markdown
    assert "NBIS" in markdown
    assert "NEBX" in markdown
    assert "QQQ" in markdown
    assert "TQQQ" in markdown


def test_format_asset_registry_markdown_includes_mappings_and_routing_fields():
    payload = registry.build_asset_registry()

    markdown = registry.format_asset_registry_markdown(payload)

    assert "## Asset Mappings" in markdown
    assert "## Routing Rules" in markdown
    assert "## Promotion Rules" in markdown
    assert "## Safety Guarantees" in markdown
    assert "## Limitations" in markdown
    assert "leveraged_equity_vehicle_pipeline" in markdown
    assert "leveraged_index_etf_pipeline" in markdown
    assert "AAPU" in markdown
    assert "GGLL" in markdown
    assert "NEBX" in markdown
    assert "TQQQ" in markdown


def test_format_asset_registry_markdown_validates_payload_first():
    payload = registry.build_asset_registry()
    payload["paper_trade_mode"] = False

    with pytest.raises(ValueError):
        registry.format_asset_registry_markdown(payload)


def test_static_safety_no_broker_or_robinhood_imports():
    source = Path(registry.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(registry.__file__).read_text(encoding="utf-8").lower()

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
    source = Path(registry.__file__).read_text(encoding="utf-8")

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
    source = Path(registry.__file__).read_text(encoding="utf-8")

    forbidden_write_targets = [
        "run_daily_paper_cycle.py",
        "portfolio_engine.py",
        "dividend_engine.py",
    ]

    for target in forbidden_write_targets:
        assert f'open("{target}", "w"' not in source
        assert f"open('{target}', 'w'" not in source
        assert f'Path("{target}").write_text' not in source
        assert f"Path('{target}').write_text" not in source
