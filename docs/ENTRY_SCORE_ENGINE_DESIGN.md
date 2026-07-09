# Entry Score Engine Design

## Purpose

`entry_score_engine.py` will provide the Dividend Bot Entry Score Engine.

The Entry Score Engine determines whether a ranked opportunity is at a favorable paper-trade entry point. It does not rank the attractiveness of the opportunity itself; it scores timing quality after opportunity selection.

## Scope

This is a paper-only, reporting-only strategy intelligence module.

It must not:

- Modify existing trading logic
- Modify `run_daily_paper_cycle.py`
- Modify `portfolio_engine.py`
- Modify `dividend_engine.py`
- Modify `asset_registry.py`
- Modify `market_regime_engine.py`
- Modify `market_intelligence_engine.py`
- Modify `momentum_score_engine.py`
- Modify `dividend_ranking_engine.py`
- Modify `opportunity_pairing_engine.py`
- Connect to Robinhood
- Connect to broker APIs
- Pull live internet data
- Use external APIs
- Place orders

## Inputs

Future input files:

- `opportunity_pairing_report.json`
- `momentum_score_report.json`
- `market_regime_report.json`
- `market_intelligence_report.json`
- `asset_registry.json`

Current version should support deterministic fallback behavior if inputs are missing.

## Outputs

- `entry_score_report.json`
- `entry_score_report.md`

## Supported Entry Statuses

- `STRONG_ENTRY`
- `GOOD_ENTRY`
- `WAIT`
- `WATCH`
- `AVOID`
- `UNKNOWN`

Default:

- `entry_status = UNKNOWN`

## Supported Timing Contexts

- `PULLBACK_ENTRY`
- `BREAKOUT_ENTRY`
- `TREND_CONTINUATION`
- `REVERSAL_SETUP`
- `OVEREXTENDED`
- `RANGE_BOUND`
- `UNKNOWN`

Default:

- `timing_context = UNKNOWN`

## Public Dataclasses

### EntrySignal

Represents one entry-quality signal.

Fields:

- `signal_name`
- `score`
- `status`
- `confidence`
- `confidence_level`
- `timing_context`
- `risk_flags`
- `recommendations`
- `warnings`
- `source`
- `last_updated_utc`

Default signal behavior:

- `score = 0`
- `status = UNKNOWN`
- `confidence = 0.0`
- `confidence_level = LOW`
- `timing_context = UNKNOWN`
- `source = deterministic_fallback`

### EntryScoreReport

Represents the full exportable entry score report.

Fields:

- `bot_name`
- `bot_type`
- `module_name`
- `module_version`
- `schema_version`
- `generated_by`
- `generated_at_utc`
- `paper_trade_mode`
- `live_trading_enabled`
- `broker_execution_enabled`
- `reporting_only`
- `supported_entry_statuses`
- `supported_timing_contexts`
- `entry_signal_names`
- `entry_signals`
- `entry_score`
- `entry_status`
- `confidence`
- `confidence_level`
- `timing_context`
- `risk_flags`
- `recommendations`
- `warnings`
- `errors`
- `scoring_model`
- `timing_model`
- `confirmation_model`
- `risk_flag_model`
- `recommendation_model`
- `integration_targets`
- `safety_guarantees`
- `limitations`

## Public Functions

- `build_entry_score_report()`
- `validate_entry_score_report(payload)`
- `write_entry_score_report_json(path="entry_score_report.json")`
- `read_entry_score_report_json(path="entry_score_report.json")`
- `format_entry_score_report_markdown(payload)`
- `write_entry_score_report_markdown(path="entry_score_report.md")`

## Default v1.0 Behavior

Current version should be deterministic fallback only:

- `entry_score = 0`
- `entry_status = UNKNOWN`
- `confidence = 0.0`
- `confidence_level = LOW`
- `timing_context = UNKNOWN`
- No live data inputs consumed
- No external API calls

## Entry Signal Names

- `pullback_quality`
- `breakout_quality`
- `trend_confirmation`
- `momentum_confirmation`
- `market_regime_confirmation`
- `market_intelligence_confirmation`
- `volatility_entry_risk`
- `liquidity_entry_quality`
- `overextension_risk`
- `self_funding_confirmation`

## Scoring Model

Future score range:

- `0` to `100`

Suggested interpretation:

- `85 to 100` = STRONG_ENTRY
- `75 to 84` = GOOD_ENTRY
- `60 to 74` = WATCH
- `45 to 59` = WAIT
- `0 to 44` = AVOID
- Missing/no data = UNKNOWN

Current fallback:

- `entry_score = 0`
- `entry_status = UNKNOWN`

## Confidence Model

Confidence range:

- `0.0` to `1.0`

Confidence levels:

- `0.00 to 0.39` = LOW
- `0.40 to 0.69` = MEDIUM
- `0.70 to 1.00` = HIGH

Default:

- `confidence = 0.0`
- `confidence_level = LOW`

## Timing Model

The engine should distinguish between opportunity quality and entry timing.

Supported timing contexts:

- `PULLBACK_ENTRY`
- `BREAKOUT_ENTRY`
- `TREND_CONTINUATION`
- `REVERSAL_SETUP`
- `OVEREXTENDED`
- `RANGE_BOUND`
- `UNKNOWN`

Current fallback:

- `timing_context = UNKNOWN`

## Integration Rules

### Opportunity Pairing Engine

Entry Score consumes opportunity candidates after they have already been ranked for income + growth potential.

Entry Score must not replace Opportunity Pairing.

### Momentum Score Engine

Momentum confirmation may improve entry quality.

Weak, mixed, or unknown momentum should reduce confidence or preserve fallback status.

### Market Regime Engine

Bullish regimes may confirm entry quality.

Bearish or high-volatility regimes may reduce entry quality and add risk flags.

### Market Intelligence Engine

Positive intelligence may confirm entry quality.

Negative or mixed intelligence may reduce confidence and add risk flags.

### Asset Registry

Asset type can affect entry criteria.

Examples:

- Leveraged ETFs require stronger confirmation.
- Income ETFs may allow lower momentum requirements.
- Unknown assets should require manual review.

## Validation Rules

Validation should enforce:

- `paper_trade_mode=True`
- `live_trading_enabled=False`
- `broker_execution_enabled=False`
- `reporting_only=True`
- Required fields exist
- `supported_entry_statuses` matches approved list
- `supported_timing_contexts` matches approved list
- `entry_signal_names` matches approved list
- `entry_signals` is a non-empty list
- Each signal has required fields
- Signal names are supported
- Signal score is between 0 and 100
- Signal confidence is between 0.0 and 1.0
- Signal confidence_level is LOW, MEDIUM, or HIGH
- Signal timing_context is supported
- `entry_score` is between 0 and 100
- `entry_status` is supported
- `confidence` is between 0.0 and 1.0
- `confidence_level` is LOW, MEDIUM, or HIGH
- `timing_context` is supported
- `risk_flags`, `recommendations`, `warnings`, and `errors` are lists
- List entries are non-empty strings
- Malformed payload raises `ValueError`
- Missing required fields raise `ValueError`

## Safety Guarantees

- Paper-only
- Reporting only
- No brokerage execution
- No Robinhood execution
- No live trading
- No order placement
- No subprocess usage
- No `os.system` usage
- No live internet data pull
- No external API usage
- Read-only analysis only

## Testing Plan

Tests should verify:

- Dataclasses exist
- Public functions exist
- Default report is valid
- Default fallback values are correct
- All entry signals exist
- Validation catches malformed payloads
- Validation catches missing required fields
- Validation catches invalid statuses
- Validation catches invalid timing contexts
- Validation catches invalid confidence values
- JSON write/read round trip
- Markdown generation
- Static safety checks for broker, Robinhood, subprocess, `os.system`, live internet, and order placement logic

## Scope Boundary

`entry_score_engine.py` should only provide a stable, validated, paper-only entry timing interface.

It should not promote assets, demote assets, allocate capital, execute trades, or modify portfolio state.
