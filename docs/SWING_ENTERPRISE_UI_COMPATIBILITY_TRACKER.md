# Swing Enterprise UI Compatibility Tracker

## Purpose

This living document records every Enterprise AI CIO dashboard/evidence change made in the Dividend Bot repository that the external Swing strategy may need to mirror so that SWING-001 displays correctly on jshouseapi.com.

The Dividend Bot remains the Enterprise AI CIO host. The Swing repository must not duplicate the host UI. Instead, it should publish strategy-scoped evidence that conforms to the Enterprise contracts consumed by the Dividend host.

This document must be updated whenever a new Enterprise dashboard field, evidence contract, or presentation requirement is introduced.

## Permanent architecture and safety rules

- The Dividend Bot is the Enterprise AI CIO host.
- The Swing Bot is an external registered strategy/plugin.
- Do not copy Dividend strategy logic into Swing.
- Do not create a second Enterprise AI CIO inside Swing.
- Do not change investor allocation or activation policy as part of UI work.
- Preserve paper-only behavior.
- Preserve `automatic_activation_allowed = false`.
- Preserve `live_trading_enabled = false`.
- Preserve `broker_execution_enabled = false`.
- Preserve `order_placement_enabled = false`.
- Preserve `capital_movement_enabled = false`.
- Strategy evidence must remain strategy-scoped; SWING-001 evidence must never be inferred from DIVIDEND-001 artifacts.
- Missing evidence must remain visibly missing rather than being fabricated.

## Current Enterprise strategy KPI contract

For the host dashboard to render a strategy cleanly, the normalized strategy row can expose the following fields when evidence exists:

- `strategy_id`
- `display_name`
- `strategy_type`
- `lifecycle_status`
- `runtime_status`
- `health_status`
- `readiness`
- `enabled`
- `paper_trade_mode`
- `paper_compatible`
- `advisory_only`
- `reporting_only`
- `allocated_capital`
- `portfolio_value`
- `position_count`
- `holdings`
- `positions`
- `watchlist_count`
- `watchlist`
- `income`
- `income_events`
- `realized_gain`
- `unrealized_gain`
- `win_rate_percent`
- `opportunity_quality`
- `performance_detail`
- `alerts`
- `risk_flags`
- `decision_journal`
- `decision_journal_status`
- `decision_journal_path`
- `capabilities`
- `published_artifacts`
- `evidence_paths`
- `evidence_status`

The Enterprise host is responsible for rendering these fields. Swing is responsible only for publishing authoritative SWING-001 evidence that can be normalized into them.

## Development log

### 2026-08-07 — Strategy identity and allocation scoping

Dividend-side development added canonical strategy-ID handling so strategy allocations and KPI evidence remain scoped to the correct strategy.

Swing compatibility requirement:

- Publish the canonical ID exactly as `SWING-001`.
- Do not use alternate IDs such as `swing`, `SWING`, or repository names in strategy-owned KPI rows unless the registration adapter explicitly canonicalizes them.
- Allocation evidence must remain strategy-specific. SWING-001 should report/use its own allocation value and must never emit the Enterprise total as its strategy allocation.

Current expected Enterprise allocation relationship:

- DIVIDEND-001: strategy-specific allocation.
- SWING-001: strategy-specific allocation.
- Enterprise total: host-owned aggregate only.

### 2026-08-07 — Opportunity Quality evidence

The Enterprise host now displays a normalized `opportunity_quality` KPI for each strategy.

Swing compatibility requirement:

- Publish a numeric Opportunity Quality value in the Swing Enterprise evidence artifact.
- Keep the score bounded to the Swing strategy's authoritative Opportunity Quality contract.
- The host must not recalculate Swing Opportunity Quality from Dividend evidence.
- SWING-001 should preserve provenance to the Swing-owned Opportunity Quality artifact.

Known Swing artifact expectation currently declared by the host:

- `main/results/opportunity_quality_report.json`

If Swing uses a different canonical file name, its Enterprise registry declaration must point to the actual artifact path and schema.

### 2026-08-07 — Detailed Holdings evidence

Dividend-side development added a normalized detailed Holdings contract and a professional table renderer.

The host renderer expects `holdings` or `positions` to be a list of strategy-owned mappings. The professional table can use these fields per row when available:

- `symbol`
- `pair`
- `sleeve`
- `position_status`
- `shares`
- `price`
- `market_value`
- `source`

The host calculates `% Portfolio` from `market_value / portfolio_value` for display only.

Swing compatibility requirement:

- Publish actual SWING-001 open positions/holdings as structured rows rather than only a position count.
- `position_count` should match the number of holdings rows the strategy wants represented in the workspace.
- Each row should identify symbol, quantity/shares, current price, market value, status, and evidence source when those values exist.
- Do not fabricate shares, price, market value, P/L, or cost basis if Swing does not have authoritative evidence.
- Reserve/cash rows may be represented explicitly if Swing treats reserve capital as a strategy-owned holding.
- Use strategy-owned evidence paths only.

Current host behavior:

- `OPEN` renders as an open-position badge.
- `PARKED`/`CASH`/`RESERVE` renders as a reserve badge.
- Lock statuses render as warnings.
- Missing P/L remains unreported.

### 2026-08-07 — Watchlist detail

The Enterprise host supports both `watchlist_count` and structured `watchlist` rows.

Swing compatibility requirement:

- Continue publishing the authoritative Swing watchlist artifact.
- Normalize candidate/watchlist rows so the host can identify at minimum `symbol` and status.
- Additional strategy-owned fields may be preserved, such as rank, score, committee decision, market-data state, or evidence source.
- Do not rely only on `watchlist_count`; detailed rows are required for a professional Watchlist tab.

Known Swing artifact currently readable by the host:

- `main/results/watchlist_report.json`

### 2026-08-07 — Performance detail contract

The Enterprise host supports scalar performance KPIs and a nested `performance_detail` structure.

Swing compatibility requirement:

Where authoritative Swing evidence exists, publish or make discoverable:

- `trade_count`
- `closed_trade_count`
- `open_trade_count`
- `win_count`
- `loss_count`
- `flat_count`
- `win_rate_percent`
- `closed_trades`
- `open_trades`
- `realized_gain`
- `unrealized_gain`

The host should display only evidence actually supplied by Swing.

Known Swing evidence currently declared by the host includes:

- `main/results/stock_performance_report.json`
- `main/results/weekly_stock_report.json`
- `main/results/monthly_command_center.json`

These declared paths must exist at runtime or be corrected in the Swing Enterprise registration to the actual canonical paths.

### 2026-08-07 — Alerts and risk flags

The Enterprise host accepts strategy-scoped `alerts` and `risk_flags` arrays.

Swing compatibility requirement:

- Publish structured Swing alerts/risk flags if the strategy has authoritative lifecycle, earnings, market-data, portfolio-risk, or governance warnings.
- Each alert should be strategy-scoped and should include a type/category, severity/status, and human-readable evidence where available.
- Do not convert missing evidence into a false all-clear status.

Known Swing artifacts currently declared by the host that may supply this information:

- `main/results/portfolio_risk.json`
- `main/results/position_lifecycle.json`
- `main/results/market_data_refresh_status.json`
- `main/results/swing_daily_cycle_report.json`

### 2026-08-07 — Decision Journal

The Enterprise host has a dedicated Decision Journal renderer and rejects cross-strategy journals.

Swing compatibility requirement:

- Publish a SWING-001-owned Decision Journal using the Enterprise decision-journal contract expected by the host.
- The journal's `strategy_id` must equal `SWING-001`.
- Preserve paper-only/read-only safety flags.
- Committee evidence, decision sequence, vote/reason, and supporting evidence may be exposed when authoritative.
- Do not point SWING-001 to a Dividend journal.

Current host fields:

- `decision_journal`
- `decision_journal_status`
- `decision_journal_path`
- `decision_count`

## Current known Swing runtime gaps observed by the Enterprise host

The Dividend-host dashboard has recently reported the following SWING-001 declared artifacts as missing on the DigitalOcean runtime:

- `main/results/market_data_refresh_status.json`
- `main/results/monthly_command_center.json`
- `main/results/opportunity_quality_report.json`
- `main/results/portfolio_risk.json`
- `main/results/position_lifecycle.json`
- `main/results/stock_performance_report.json`
- `main/results/swing_daily_cycle_report.json`
- `main/results/weekly_stock_report.json`

These should not be manually copied into the Dividend repository. Swing should either generate them at its declared canonical paths or update its Enterprise registration so the host resolves the correct existing paths relative to the Swing repository.

## UI 2.0 compatibility principle

The professional UI is host-owned. Swing does not need to duplicate CSS or HTML from the Dividend repository.

For each UI 2.0 development step, Swing only needs to ensure its published Enterprise evidence supplies the same semantic contract. For example, the new professional Holdings table is reusable for SWING-001 automatically once the host receives structured SWING-001 holdings rows.

## Next updates to this tracker

As UI 2.0 development continues, append Swing compatibility notes for:

1. Portfolio summary and attribution.
2. Professional Watchlist table.
3. Income/cash-flow presentation where applicable to Swing.
4. Detailed Performance dashboard.
5. Alerts and risk presentation.
6. Decision Journal presentation.
7. Position Analytics fields such as cost basis, unrealized P/L, return, and daily change.
8. Any new Enterprise contract or schema field introduced by the host.

## Handoff rule

When the Dividend-side UI/evidence work is complete, this file should be provided to the Swing Bot development chat as the authoritative compatibility checklist. Swing changes should be implemented only in the Swing repository, while host rendering and aggregation changes remain in the Dividend repository.
