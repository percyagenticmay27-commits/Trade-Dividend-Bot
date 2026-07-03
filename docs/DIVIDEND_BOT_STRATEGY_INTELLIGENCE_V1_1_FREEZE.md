# Dividend Bot Strategy Intelligence Layer v1.1 Freeze

## Project

Tradebot_Dividend_bot

## Reference

- DIVIDEND_BOT_OPERATIONAL_V1_0_FREEZE.md

## Frozen Module

- asset_registry.py

## Verified Test Results

asset_registry.py

38 passed

0 failed

Compile status: source verified through successful pytest import and execution.

## Purpose

Strategy Intelligence v1.1 introduces the foundational Asset Registry & Classification Engine.

Trading logic remains unchanged. Paper trading remains enforced. Existing portfolio logic, report generation, and runtime workflow remain unchanged.

## Responsibilities

asset_registry.py provides:

- Canonical asset registry
- Underlying to preferred trading vehicle mapping
- One-to-many candidate mappings
- Asset classification
- Strategy pipeline routing
- Promotion eligibility metadata
- Registry validation
- JSON export
- Markdown export
- Read-only lookup services

## Supported Classifications

- UNDERLYING_EQUITY
- LEVERAGED_ETF
- INCOME_ETF
- OPTION_STRATEGY_ETF
- SECTOR_ETF
- THEMATIC_ETF
- BROAD_MARKET_ETF
- CRYPTO_ETF
- COMMODITY_ETF
- SPECIALTY_ETF
- UNKNOWN

## Initial Registry Mappings

- AAPL -> AAPU
- GOOGL -> GGLL
- NBIS -> NEBX
- QQQ -> TQQQ

## Public Interface

- build_asset_registry()
- validate_asset_registry(payload)
- write_asset_registry_json()
- read_asset_registry_json()
- format_asset_registry_markdown()
- write_asset_registry_markdown()
- get_asset_mapping()
- get_preferred_vehicle()
- get_candidate_vehicles()
- classify_asset()
- is_promotion_eligible()
- get_strategy_pipeline()

## Safety Guarantees

- paper_trade_mode=True
- live_trading_enabled=False
- broker_execution_enabled=False
- No Robinhood execution
- No broker execution
- No real order placement
- No subprocess execution
- No os.system execution

## Freeze Declaration

Dividend Bot Strategy Intelligence Layer v1.1 is complete and asset_registry.py is frozen.
