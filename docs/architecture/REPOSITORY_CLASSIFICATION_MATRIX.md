# Repository Classification Matrix

**Version:** 1.0.0  
**Status:** FROZEN FOR PLATFORM V1 FOUNDATION  
**Repository:** Trade-Dividend-Bot  
**Branch:** `platform-v1-foundation`

## Purpose

This document assigns existing modules to their long-term architectural owners without moving files or changing imports. It is the first controlled step in evolving the existing Dividend Bot into a strategy-neutral investment platform whose first production strategy package is Dividend.

## Governing Rules

1. Existing working behavior is preserved during classification.
2. Classification does not authorize file moves or rewrites.
3. Shared intelligence is owned by the platform.
4. Strategy-specific policy and interpretation are owned by the strategy package.
5. Dividend, Swing, Options, and future strategies must keep separate decisions, performance, reports, audits, and learning histories.
6. Shared renderers and infrastructure may be reused, but strategy report content must never be merged.
7. Paper-only operation remains mandatory for Platform Version 1.

## Architectural Ownership

### Platform Foundation

Representative modules:

- `bot_capabilities.py`
- `bot_environment_check.py`
- `bot_report_integrity.py`
- `bot_runtime_metrics.py`
- `bot_diagnostics.py`
- `historical_archive_manager.py`
- `market_data_provider.py`
- `paper_portfolio_config.py`
- `run_daily_paper_cycle.py`
- `master_portfolio_orchestrator.py`

Responsibilities:

- Configuration and paper-only enforcement
- Runtime orchestration
- Health and integrity checks
- Archival and operational lifecycle
- Shared market-data access

### Company and Market Intelligence

Representative modules:

- `candidate_discovery_engine.py`
- `market_intelligence_engine.py`
- `market_regime_engine.py`
- `institutional_context_pattern_intelligence.py`
- `earnings_engine.py`
- `indicators.py`
- `conviction_engine.py`
- `research_intelligence_engine.py`
- `opportunity_rotation_forecast_engine.py`

Responsibilities:

- Discovery
- Market and institutional context
- Earnings intelligence
- Shared technical calculations
- Regime and conviction evidence
- Opportunity intelligence

These modules provide facts and scores. They must not own Dividend-, Swing-, or Options-specific investment policy.

### Evidence and Governance

Representative modules:

- `ai_cio_evidence_registry.py`
- `ai_cio_decision_record.py`
- `ai_cio_decision_engine.py`
- `ai_cio_system_integrator.py`
- `decision_stability_engine.py`
- `ai_cio_missed_opportunity_review.py`

Responsibilities:

- Append-only evidence history
- Constitutional decision governance
- Decision records and stability
- Original decision preservation
- Investor override traceability

The AI CIO is the only automated authority that may issue the final governed investment decision. Committees and supporting engines analyze and recommend only.

### Portfolio Platform

Representative modules:

- `portfolio_engine.py`
- `portfolio_lifecycle_engine.py`
- `portfolio_lifecycle_manager.py`
- `portfolio_intelligence_engine.py`
- `portfolio_decision_engine.py`
- `portfolio_forecast_engine.py`
- `portfolio_health_engine.py`
- `portfolio_history_engine.py`
- `portfolio_rebalance_engine.py`
- `master_portfolio_strategy_engine.py`
- `opportunity_replacement_manager.py`

Responsibilities:

- Shared holdings and paper positions
- Position lifecycle
- Allocation and rebalance infrastructure
- Portfolio-level risk and health
- Strategy attribution by position or sleeve

The portfolio may aggregate holdings operationally, but strategy returns and strategy decisions remain isolated.

### Dividend Strategy

Representative modules:

- `dividend_engine.py`
- `dividend_ranking_engine.py`
- `income_reinvestment_engine.py`
- `dividend_earnings_risk_manager.py`
- `dividend_rankings.py`
- `dividend_strategy`-specific configuration and reports

Responsibilities:

- Dividend eligibility and ranking policy
- Income policy
- Dividend safety interpretation
- Dividend-specific entry, hold, exit, and reinvestment behavior
- Dividend-only decisions, reports, audits, and learning history

### Strategy Framework and Simulation

Representative modules:

- `strategy_learning_engine.py`
- `strategy_health_dashboard.py`
- `strategy_performance_analytics.py`
- `baseline_backtest.py`
- `earnings_backtest.py`
- `run_walk_forward_validation.py`
- `run_weighted_hybrid_optimization.py`
- `signal_model_etf.py`
- `signal_model_underlying.py`

Responsibilities:

- Shared strategy registration and lifecycle infrastructure
- Backtesting and historical replay
- Walk-forward validation
- Strategy-scoped performance and learning inputs

Shared infrastructure must store and retrieve results using an explicit `strategy_id` or equivalent scope.

### Reporting

Representative modules:

- `weekly_portfolio_report.py`
- `monthly_portfolio_report.py`
- `daily_portfolio_command_center.py`
- `performance_analytics_dashboard.py`
- `generate_performance_report.py`
- `ai_cio_executive_dashboard.py`
- `ai_cio_weekly_board_letter.py`

Responsibilities:

- Shared rendering and export utilities
- Dividend daily, weekly, monthly, and audit reports
- Future Swing daily, weekly, monthly, and audit reports
- Platform health and governance reports

The same template may be reused, but each strategy report must contain only that strategy's positions, returns, decisions, recommendations, audit results, and learning observations.

### Audit and Release Governance

Representative modules:

- `version_1_0_release_audit.py`
- `validate_universe.py`
- `generate_live_readiness_tracker.py`
- health-check and deployment scripts

Responsibilities:

- Release gates
- Data and universe validation
- Paper-only readiness
- Deployment readiness
- Platform audit and strategy-specific audit separation

## Output Ownership

| Output family | Owner | Isolation rule |
|---|---|---|
| Platform health and integrity | Platform | May summarize all services, not combine strategy returns |
| Company intelligence | Platform | Shared factual intelligence |
| Evidence timeline | Platform | Shared append-only evidence |
| AI CIO decision record | Governance | Must include strategy scope when a decision is strategy-specific |
| Dividend reports and audits | Dividend Strategy | Dividend-only |
| Swing reports and audits | Swing Strategy | Swing-only |
| Options reports and audits | Options Strategy | Options-only |
| Portfolio holdings | Portfolio Platform | May aggregate shares while preserving strategy attribution |
| Strategy performance | Owning strategy | Never merged into another strategy's report |

## Initial Dependency Direction

```text
Platform Foundation
        ↓
Company and Market Intelligence
        ↓
Evidence and Governance
        ↓
Portfolio Platform
        ↓
Strategy Framework
        ↓
Dividend Strategy
        ↓
Strategy-Specific Reporting and Auditing
```

A lower-level shared module must not import a strategy-specific module.

## Controlled Migration Rule

Files remain in their current locations until a tested migration task explicitly authorizes a move. The first implementation cycle will add contracts, registries, strategy identifiers, and adapters around existing modules before considering physical reorganization.

## Freeze Statement

This classification matrix is frozen for the Platform Version 1 Foundation. Changes require an Architecture Decision Record and must preserve paper-only operation, strategy isolation, and existing Dividend Bot compatibility.
