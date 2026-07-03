"""
Read-only Asset Registry & Classification Engine for Dividend Bot v1.1.

This module provides an authoritative source of truth for tradable symbols,
underlying-to-preferred-vehicle mappings, classification metadata, promotion
eligibility, and strategy pipeline routing.

It does not modify trading logic, runtime workflow files, portfolio logic,
dividend logic, or broker state.

PAPER ONLY:
- paper_trade_mode is always True
- live_trading_enabled is always False
- broker_execution_enabled is always False
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


MODULE_NAME = "asset_registry"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
GENERATED_BY = "Agentic-Robin-Dividend.bot"

REGISTRY_NAME = "Dividend Bot Asset Registry"
BOT_NAME = "Agentic Robin Dividend Bot"
BOT_TYPE = "paper_dividend_etf_management"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

UNDERLYING_EQUITY = "UNDERLYING_EQUITY"
LEVERAGED_ETF = "LEVERAGED_ETF"
INCOME_ETF = "INCOME_ETF"
OPTION_STRATEGY_ETF = "OPTION_STRATEGY_ETF"
SECTOR_ETF = "SECTOR_ETF"
THEMATIC_ETF = "THEMATIC_ETF"
BROAD_MARKET_ETF = "BROAD_MARKET_ETF"
CRYPTO_ETF = "CRYPTO_ETF"
COMMODITY_ETF = "COMMODITY_ETF"
SPECIALTY_ETF = "SPECIALTY_ETF"
UNKNOWN = "UNKNOWN"

SUPPORTED_CLASSIFICATIONS = [
    UNDERLYING_EQUITY,
    LEVERAGED_ETF,
    INCOME_ETF,
    OPTION_STRATEGY_ETF,
    SECTOR_ETF,
    THEMATIC_ETF,
    BROAD_MARKET_ETF,
    CRYPTO_ETF,
    COMMODITY_ETF,
    SPECIALTY_ETF,
    UNKNOWN,
]

VALID_LEVERAGE_VALUES = {"1x", "2x", "3x", None}

ASSET_MAPPING_REQUIRED_FIELDS = [
    "symbol",
    "classification",
    "preferred_symbol",
    "fallback_symbol",
    "preferred_vehicle_classification",
    "candidate_symbols",
    "leverage",
    "strategy_pipeline",
    "promotion_eligible",
    "promotion_reason",
    "requires_manual_review",
    "risk_class",
    "max_allocation_hint",
    "preferred_for_paper_strategy",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "notes",
]

REGISTRY_REQUIRED_FIELDS = [
    "registry_name",
    "bot_name",
    "bot_type",
    "registry_version",
    "schema_version",
    "generated_at_utc",
    "generated_by",
    "module_name",
    "module_version",
    "paper_trade_mode",
    "live_trading_enabled",
    "broker_execution_enabled",
    "supported_classifications",
    "asset_mappings",
    "routing_rules",
    "promotion_rules",
    "safety_guarantees",
    "limitations",
]

LIST_FIELDS = [
    "supported_classifications",
    "asset_mappings",
    "routing_rules",
    "promotion_rules",
    "safety_guarantees",
    "limitations",
]

SAFETY_GUARANTEES = [
    "paper_trade_mode is enforced as True",
    "live_trading_enabled is enforced as False",
    "broker_execution_enabled is enforced as False",
    "no broker execution is performed",
    "no external brokerage execution is performed",
    "no real order placement is performed",
    "no trading strategy logic is modified",
    "run_daily_paper_cycle.py is not modified",
    "portfolio_engine.py is not modified",
    "dividend_engine.py is not modified",
    "only local registry JSON and Markdown outputs are written when explicitly requested",
]

LIMITATIONS = [
    "Registry mappings provide classification and routing metadata only.",
    "Registry mappings do not execute trades or modify portfolio allocations.",
    "Automatic ETF discovery is not enabled in this module version.",
    "Discovered future candidates should require manual review before strategy use.",
]

ROUTING_RULES = [
    "UNDERLYING_EQUITY with LEVERAGED_ETF preferred vehicle routes to leveraged_equity_vehicle_pipeline.",
    "BROAD_MARKET_ETF with LEVERAGED_ETF preferred vehicle routes to leveraged_index_etf_pipeline.",
    "INCOME_ETF routes to dividend_income_pipeline.",
    "OPTION_STRATEGY_ETF routes to income_option_strategy_pipeline.",
    "UNKNOWN routes to manual_review_pipeline.",
]

PROMOTION_RULES = [
    "Only paper-trading promotion is supported.",
    "Promotion eligibility does not authorize broker execution.",
    "Leveraged vehicles require high-risk classification.",
    "Future discovered candidates must remain requires_manual_review=True until validated.",
]


@dataclass(frozen=True)
class AssetMapping:
    """One authoritative asset mapping entry."""

    symbol: str
    classification: str
    preferred_symbol: str
    fallback_symbol: str
    preferred_vehicle_classification: str
    candidate_symbols: List[str]
    leverage: Optional[str]
    strategy_pipeline: str
    promotion_eligible: bool
    promotion_reason: str
    requires_manual_review: bool
    risk_class: str
    max_allocation_hint: Optional[str]
    preferred_for_paper_strategy: bool
    paper_trade_mode: bool = PAPER_TRADE_MODE
    live_trading_enabled: bool = LIVE_TRADING_ENABLED
    broker_execution_enabled: bool = BROKER_EXECUTION_ENABLED
    notes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AssetRegistryPayload:
    """Full exportable asset registry payload."""

    registry_name: str
    bot_name: str
    bot_type: str
    registry_version: str
    schema_version: str
    generated_at_utc: str
    generated_by: str
    module_name: str
    module_version: str
    paper_trade_mode: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    supported_classifications: List[str]
    asset_mappings: List[Dict[str, Any]]
    routing_rules: List[str]
    promotion_rules: List[str]
    safety_guarantees: List[str]
    limitations: List[str]


def _utc_now_iso() -> str:
    """Return a stable UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _initial_asset_mappings() -> List[AssetMapping]:
    """Return the initial frozen v1.1 asset mappings."""
    return [
        AssetMapping(
            symbol="AAPL",
            classification=UNDERLYING_EQUITY,
            preferred_symbol="AAPU",
            fallback_symbol="AAPL",
            preferred_vehicle_classification=LEVERAGED_ETF,
            candidate_symbols=["AAPU", "AAPL"],
            leverage="2x",
            strategy_pipeline="leveraged_equity_vehicle_pipeline",
            promotion_eligible=True,
            promotion_reason="Preferred 2x leveraged paper-trading vehicle for AAPL exposure.",
            requires_manual_review=False,
            risk_class="HIGH",
            max_allocation_hint="strategy_defined",
            preferred_for_paper_strategy=True,
            notes=["Fallback remains the underlying equity AAPL."],
        ),
        AssetMapping(
            symbol="GOOGL",
            classification=UNDERLYING_EQUITY,
            preferred_symbol="GGLL",
            fallback_symbol="GOOGL",
            preferred_vehicle_classification=LEVERAGED_ETF,
            candidate_symbols=["GGLL", "GOOGL"],
            leverage="2x",
            strategy_pipeline="leveraged_equity_vehicle_pipeline",
            promotion_eligible=True,
            promotion_reason="Preferred 2x leveraged paper-trading vehicle for GOOGL exposure.",
            requires_manual_review=False,
            risk_class="HIGH",
            max_allocation_hint="strategy_defined",
            preferred_for_paper_strategy=True,
            notes=["Fallback remains the underlying equity GOOGL."],
        ),
        AssetMapping(
            symbol="NBIS",
            classification=UNDERLYING_EQUITY,
            preferred_symbol="NEBX",
            fallback_symbol="NBIS",
            preferred_vehicle_classification=LEVERAGED_ETF,
            candidate_symbols=["NEBX", "NBIS"],
            leverage="2x",
            strategy_pipeline="leveraged_equity_vehicle_pipeline",
            promotion_eligible=True,
            promotion_reason="Preferred 2x leveraged paper-trading vehicle for NBIS exposure.",
            requires_manual_review=False,
            risk_class="HIGH",
            max_allocation_hint="strategy_defined",
            preferred_for_paper_strategy=True,
            notes=["Fallback remains the underlying equity NBIS."],
        ),
        AssetMapping(
            symbol="QQQ",
            classification=BROAD_MARKET_ETF,
            preferred_symbol="TQQQ",
            fallback_symbol="QQQ",
            preferred_vehicle_classification=LEVERAGED_ETF,
            candidate_symbols=["TQQQ", "QQQ"],
            leverage="3x",
            strategy_pipeline="leveraged_index_etf_pipeline",
            promotion_eligible=True,
            promotion_reason="Preferred 3x leveraged paper-trading vehicle for QQQ exposure.",
            requires_manual_review=False,
            risk_class="HIGH",
            max_allocation_hint="strategy_defined",
            preferred_for_paper_strategy=True,
            notes=["Fallback remains the broad market ETF QQQ."],
        ),
    ]


def build_asset_registry() -> Dict[str, Any]:
    """Build the asset registry payload."""
    mappings = [asdict(mapping) for mapping in _initial_asset_mappings()]
    payload = AssetRegistryPayload(
        registry_name=REGISTRY_NAME,
        bot_name=BOT_NAME,
        bot_type=BOT_TYPE,
        registry_version=MODULE_VERSION,
        schema_version=SCHEMA_VERSION,
        generated_at_utc=_utc_now_iso(),
        generated_by=GENERATED_BY,
        module_name=MODULE_NAME,
        module_version=MODULE_VERSION,
        paper_trade_mode=PAPER_TRADE_MODE,
        live_trading_enabled=LIVE_TRADING_ENABLED,
        broker_execution_enabled=BROKER_EXECUTION_ENABLED,
        supported_classifications=list(SUPPORTED_CLASSIFICATIONS),
        asset_mappings=mappings,
        routing_rules=list(ROUTING_RULES),
        promotion_rules=list(PROMOTION_RULES),
        safety_guarantees=list(SAFETY_GUARANTEES),
        limitations=list(LIMITATIONS),
    )
    result = asdict(payload)
    validate_asset_registry(result)
    return result


def _require_mapping(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping/dictionary")
    return payload


def _validate_required_fields(payload: Mapping[str, Any]) -> None:
    missing = [field_name for field_name in REGISTRY_REQUIRED_FIELDS if field_name not in payload]
    if missing:
        raise ValueError(f"missing required field(s): {', '.join(missing)}")


def _validate_exact_metadata(payload: Mapping[str, Any]) -> None:
    expected = {
        "registry_name": REGISTRY_NAME,
        "bot_name": BOT_NAME,
        "bot_type": BOT_TYPE,
        "registry_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_by": GENERATED_BY,
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
    }
    for field_name, expected_value in expected.items():
        if payload.get(field_name) != expected_value:
            raise ValueError(f"{field_name} must be {expected_value!r}")


def _is_upper_symbol(value: Any) -> bool:
    return isinstance(value, str) and value.strip() == value and value and value.upper() == value


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_string_list(value: Any, field_name: str, allow_empty: bool = False) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    if not allow_empty and not value:
        raise ValueError(f"{field_name} must not be empty")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name}[{index}] must be a non-empty string")


def _validate_asset_mapping(mapping: Any, seen_symbols: set) -> None:
    mapping = _require_mapping(mapping)
    missing = [field_name for field_name in ASSET_MAPPING_REQUIRED_FIELDS if field_name not in mapping]
    if missing:
        raise ValueError(f"asset mapping missing required field(s): {', '.join(missing)}")

    symbol = mapping["symbol"]
    preferred_symbol = mapping["preferred_symbol"]
    fallback_symbol = mapping["fallback_symbol"]
    candidate_symbols = mapping["candidate_symbols"]

    for field_name in ["symbol", "preferred_symbol", "fallback_symbol"]:
        if not _is_upper_symbol(mapping.get(field_name)):
            raise ValueError(f"{field_name} must be a non-empty uppercase string")

    if symbol in seen_symbols:
        raise ValueError(f"duplicate primary symbol: {symbol}")
    seen_symbols.add(symbol)

    classification = mapping["classification"]
    preferred_classification = mapping["preferred_vehicle_classification"]

    if classification not in SUPPORTED_CLASSIFICATIONS:
        raise ValueError(f"classification is not supported: {classification}")
    if preferred_classification not in SUPPORTED_CLASSIFICATIONS:
        raise ValueError(f"preferred_vehicle_classification is not supported: {preferred_classification}")

    if not isinstance(candidate_symbols, list) or not candidate_symbols:
        raise ValueError("candidate_symbols must be a non-empty list")
    for index, candidate in enumerate(candidate_symbols):
        if not _is_upper_symbol(candidate):
            raise ValueError(f"candidate_symbols[{index}] must be a non-empty uppercase string")

    if preferred_symbol not in candidate_symbols:
        raise ValueError("preferred_symbol must appear in candidate_symbols")
    if fallback_symbol not in candidate_symbols:
        raise ValueError("fallback_symbol must appear in candidate_symbols")

    if mapping["leverage"] not in VALID_LEVERAGE_VALUES:
        raise ValueError('leverage must be "1x", "2x", "3x", or None')

    _validate_non_empty_string(mapping["strategy_pipeline"], "strategy_pipeline")
    _validate_non_empty_string(mapping["promotion_reason"], "promotion_reason")
    _validate_non_empty_string(mapping["risk_class"], "risk_class")

    if not isinstance(mapping["promotion_eligible"], bool):
        raise ValueError("promotion_eligible must be a boolean")
    if not isinstance(mapping["requires_manual_review"], bool):
        raise ValueError("requires_manual_review must be a boolean")
    if not isinstance(mapping["preferred_for_paper_strategy"], bool):
        raise ValueError("preferred_for_paper_strategy must be a boolean")

    allocation_hint = mapping["max_allocation_hint"]
    if allocation_hint is not None:
        _validate_non_empty_string(allocation_hint, "max_allocation_hint")

    if mapping["paper_trade_mode"] is not True:
        raise ValueError("asset mapping paper_trade_mode must be True")
    if mapping["live_trading_enabled"] is not False:
        raise ValueError("asset mapping live_trading_enabled must be False")
    if mapping["broker_execution_enabled"] is not False:
        raise ValueError("asset mapping broker_execution_enabled must be False")

    _validate_string_list(mapping["notes"], "notes", allow_empty=True)


def validate_asset_registry(payload: Any) -> bool:
    """Validate an asset registry payload and raise ValueError on failure."""
    payload = _require_mapping(payload)
    _validate_required_fields(payload)
    _validate_exact_metadata(payload)
    _validate_non_empty_string(payload.get("generated_at_utc"), "generated_at_utc")

    for field_name in LIST_FIELDS:
        if not isinstance(payload.get(field_name), list):
            raise ValueError(f"{field_name} must be a list")

    if payload["supported_classifications"] != SUPPORTED_CLASSIFICATIONS:
        raise ValueError("supported_classifications must match the frozen supported classification list")

    _validate_string_list(payload["routing_rules"], "routing_rules")
    _validate_string_list(payload["promotion_rules"], "promotion_rules")
    _validate_string_list(payload["safety_guarantees"], "safety_guarantees")
    _validate_string_list(payload["limitations"], "limitations")

    asset_mappings = payload["asset_mappings"]
    if not isinstance(asset_mappings, list) or not asset_mappings:
        raise ValueError("asset_mappings must be a non-empty list")

    seen_symbols: set = set()
    for mapping in asset_mappings:
        _validate_asset_mapping(mapping, seen_symbols)

    return True


def write_asset_registry_json(path: str = "asset_registry.json") -> Dict[str, Any]:
    """Build, validate, and write asset_registry.json."""
    payload = build_asset_registry()
    validate_asset_registry(payload)

    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def read_asset_registry_json(path: str = "asset_registry.json") -> Dict[str, Any]:
    """Read and validate an asset registry JSON file."""
    input_path = Path(path)
    with input_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    validate_asset_registry(payload)
    return payload


def _registry_mapping_index(payload: Optional[Mapping[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
    registry = payload if payload is not None else build_asset_registry()
    validate_asset_registry(registry)
    return {mapping["symbol"]: mapping for mapping in registry["asset_mappings"]}


def _normalize_symbol(symbol: str) -> str:
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValueError("symbol must be a non-empty string")
    return symbol.strip().upper()


def get_asset_mapping(symbol: str) -> Optional[Dict[str, Any]]:
    """Return the registry mapping for a symbol, or None if unknown."""
    normalized = _normalize_symbol(symbol)
    return _registry_mapping_index().get(normalized)


def get_preferred_vehicle(symbol: str) -> Optional[str]:
    """Return the preferred vehicle for a symbol, or None if unknown."""
    mapping = get_asset_mapping(symbol)
    if mapping is None:
        return None
    return mapping["preferred_symbol"]


def get_candidate_vehicles(symbol: str) -> List[str]:
    """Return candidate vehicles for a symbol, or an empty list if unknown."""
    mapping = get_asset_mapping(symbol)
    if mapping is None:
        return []
    return list(mapping["candidate_symbols"])


def classify_asset(symbol: str) -> str:
    """Return the registry classification for a symbol, or UNKNOWN if unknown."""
    mapping = get_asset_mapping(symbol)
    if mapping is None:
        return UNKNOWN
    return mapping["classification"]


def is_promotion_eligible(symbol: str) -> bool:
    """Return whether a symbol is eligible for paper-strategy promotion."""
    mapping = get_asset_mapping(symbol)
    if mapping is None:
        return False
    return bool(mapping["promotion_eligible"])


def get_strategy_pipeline(symbol: str) -> str:
    """Return the strategy pipeline for a symbol, or manual_review_pipeline if unknown."""
    mapping = get_asset_mapping(symbol)
    if mapping is None:
        return "manual_review_pipeline"
    return mapping["strategy_pipeline"]


def _format_list(title: str, values: List[str]) -> List[str]:
    lines = [f"## {title}"]
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- None")
    return lines


def format_asset_registry_markdown(payload: Mapping[str, Any]) -> str:
    """Format a validated asset registry payload as Markdown."""
    validate_asset_registry(payload)

    lines = [
        f"# {payload['registry_name']}",
        "",
        f"- Bot Name: {payload['bot_name']}",
        f"- Bot Type: {payload['bot_type']}",
        f"- Registry Version: {payload['registry_version']}",
        f"- Schema Version: {payload['schema_version']}",
        f"- Generated At UTC: {payload['generated_at_utc']}",
        f"- Generated By: {payload['generated_by']}",
        f"- Paper Trade Mode: {payload['paper_trade_mode']}",
        f"- Live Trading Enabled: {payload['live_trading_enabled']}",
        f"- Broker Execution Enabled: {payload['broker_execution_enabled']}",
        "",
        "## Asset Mappings",
        "",
        "| Symbol | Classification | Preferred | Fallback | Preferred Class | Candidates | Leverage | Pipeline | Promotion Eligible | Manual Review | Risk |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]

    for mapping in payload["asset_mappings"]:
        lines.append(
            "| {symbol} | {classification} | {preferred_symbol} | {fallback_symbol} | "
            "{preferred_vehicle_classification} | {candidate_symbols} | {leverage} | "
            "{strategy_pipeline} | {promotion_eligible} | {requires_manual_review} | {risk_class} |".format(
                symbol=mapping["symbol"],
                classification=mapping["classification"],
                preferred_symbol=mapping["preferred_symbol"],
                fallback_symbol=mapping["fallback_symbol"],
                preferred_vehicle_classification=mapping["preferred_vehicle_classification"],
                candidate_symbols=", ".join(mapping["candidate_symbols"]),
                leverage=mapping["leverage"] if mapping["leverage"] is not None else "None",
                strategy_pipeline=mapping["strategy_pipeline"],
                promotion_eligible=mapping["promotion_eligible"],
                requires_manual_review=mapping["requires_manual_review"],
                risk_class=mapping["risk_class"],
            )
        )

    lines.append("")
    for title, values in [
        ("Supported Classifications", payload["supported_classifications"]),
        ("Routing Rules", payload["routing_rules"]),
        ("Promotion Rules", payload["promotion_rules"]),
        ("Safety Guarantees", payload["safety_guarantees"]),
        ("Limitations", payload["limitations"]),
    ]:
        lines.extend(_format_list(title, values))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_asset_registry_markdown(path: str = "asset_registry.md") -> Dict[str, Any]:
    """Build, validate, and write asset_registry.md."""
    payload = build_asset_registry()
    markdown = format_asset_registry_markdown(payload)
    output_path = Path(path)
    output_path.write_text(markdown, encoding="utf-8")
    return payload


if __name__ == "__main__":
    write_asset_registry_json()
    write_asset_registry_markdown()
