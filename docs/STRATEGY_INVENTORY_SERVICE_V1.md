# Strategy Inventory Service Version 1

## Purpose

Provide the AI CIO with a deterministic, read-only inventory of Enterprise strategies using published strategy contracts.

## Ownership Boundary

The service reads `manifest.json`, `status.json`, `health.json`, and `outputs.json` from contract locations supplied by Enterprise discovery or registry components.

It does not:

- import private strategy modules;
- discover market-data providers;
- register or schedule strategies;
- modify strategy contracts;
- allocate capital;
- place orders;
- communicate with a brokerage.

## Inputs

One or more strategy contract directories. Each directory may contain:

- `manifest.json`
- `status.json`
- `health.json`
- `outputs.json`

Missing or malformed contracts become visible findings and do not crash inventory generation.

## Outputs

- `results/strategy_inventory.json`
- `results/strategy_inventory.md`

## Inventory Fields

Each strategy record includes stable identity, name, type, semantic version, lifecycle, certification, runtime status, health, readiness, latest cycle, latest successful run, heartbeat, capabilities, Enterprise service dependencies, output count, contract completeness, paper-safety state, warnings, and errors.

## Summary Metrics

- strategy count
- contract-complete count
- healthy count
- warning count
- error count
- running count
- paper-safe count

## Safety

The service permanently declares:

```text
paper_trade_mode=True
live_trading_enabled=False
broker_execution_enabled=False
```

Any strategy contract that violates these declarations is flagged in the inventory.

## Public API

- `build_inventory_item`
- `build_summary`
- `build_strategy_inventory`
- `write_strategy_inventory_json`
- `render_strategy_inventory_markdown`
- `write_strategy_inventory_markdown`
- `build_and_write_strategy_inventory`

## Version 1 Non-Goals

Version 1 does not add a web UI, automatic scheduling, AI-generated recommendations, allocation logic, remote repository scanning, or live execution.
