# Enterprise Health Service Version 1

## Purpose

The Enterprise Health Service is a read-only AI CIO observability layer. It evaluates the operational condition of registered strategy plugins using Strategy Inventory data and published Enterprise contracts.

It does not inspect private strategy code and does not replace the Strategy Registry, discovery service, Enterprise Runtime, scheduler, market-data service, governance, or allocation services.

## Inputs

Primary input:

- `results/strategy_inventory.json`

The inventory is derived from each registered strategy's:

- `manifest.json`
- `status.json`
- `health.json`
- `outputs.json`

Optional input:

- Enterprise service dependency-health mapping

## Outputs

- `results/enterprise_health.json`
- `results/enterprise_health.md`

## Strategy Health Assessment

Each registered strategy receives:

- runtime status
- declared health status
- effective health status
- 0–100 health score
- score classification
- heartbeat status and age
- contract completeness
- readiness
- dependency status
- warnings and errors
- paper-only safety result

## Score Classifications

- 90–100: `HEALTHY`
- 75–89: `WARNING`
- 50–74: `DEGRADED`
- 0–49: `CRITICAL`

Errors can make the effective health status `CRITICAL` even when the numeric score is above the critical range. Paper-safety failure always forces the score to zero and effective status to `CRITICAL`.

## Enterprise Summary

The report includes:

- registered strategies
- healthy strategies
- warning strategies
- degraded strategies
- critical strategies
- offline strategies
- stale heartbeats
- average health score
- paper-safe strategies
- overall Enterprise status

## Heartbeat Rule

The default stale-heartbeat threshold is 30 minutes. The caller may provide a different positive threshold. Missing, invalid, or stale heartbeats create health findings.

## Dependency Rule

Declared `required_enterprise_services` may be evaluated against an externally supplied dependency-health mapping. The service does not perform service discovery or active network probes.

## Permanent Safety Boundaries

```text
paper_trade_mode=True
live_trading_enabled=False
broker_execution_enabled=False
```

The service must never:

- place orders
- communicate with a brokerage
- move capital
- allocate capital
- retrieve market data
- schedule strategies
- register strategies
- modify strategy state
- import private strategy modules

## Public Functions

- `classify_score`
- `assess_strategy_health`
- `build_enterprise_summary`
- `determine_enterprise_status`
- `build_enterprise_health_report`
- `load_strategy_inventory`
- `write_enterprise_health_json`
- `render_enterprise_health_markdown`
- `write_enterprise_health_markdown`
- `build_and_write_enterprise_health`

## Validation

```bash
python -m py_compile src/dividend_bot/enterprise_health_service.py
pytest tests/test_enterprise_health_service.py -v
```

The service is ready for freeze only after its targeted tests pass and the existing Strategy Inventory and repository regression tests remain green.
