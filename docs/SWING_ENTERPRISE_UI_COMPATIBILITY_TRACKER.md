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
- `available_cash` / `undeployed_cash` / `unallocated_cash` when authoritative
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
- Allocation evidence must remain strategy-specific.
- SWING-001 should report/use its own allocation value and must never emit the Enterprise total as its strategy allocation.

### 2026-08-07 — Opportunity Quality evidence

The Enterprise host now displays a normalized `opportunity_quality` KPI for each strategy.

Swing compatibility requirement:

- Publish a numeric Opportunity Quality value in the Swing Enterprise evidence artifact.
- Keep the score bounded to the Swing strategy's authoritative Opportunity Quality contract.
- Preserve provenance to the Swing-owned Opportunity Quality artifact.

Known declared host path: `main/results/opportunity_quality_report.json`.

### 2026-08-07 — Detailed Holdings evidence

The host renderer accepts strategy-owned `holdings` or `positions` rows using fields such as `symbol`, security name aliases, `pair`, `sleeve`, `position_status`, `shares`, `price`, `market_value`, and `source`.

Swing compatibility requirement:

- Publish actual SWING-001 positions as structured rows rather than only a count.
- Do not fabricate shares, price, market value, P/L, cost basis, or names if Swing does not have authoritative evidence.
- Reserve/cash rows may be explicit if Swing owns them.

### 2026-08-07 — Professional Holdings renderer wired into live workspace

The host now calls a dedicated professional Holdings renderer for every registered strategy. Swing does not need duplicate HTML or CSS; compatible structured evidence is sufficient.

### 2026-08-07 — Capital reconciliation and expanded Holdings analytics

The Holdings UI distinguishes:

- `Allocated Capital`
- `Deployed Holdings`
- `Invested Positions`
- `Cash Reserve (SGOV)` or another explicit reserve row
- `Available / Undeployed Cash`

If authoritative strategy cash is not published, the host may derive display-only undeployed cash as `allocated_capital - sum(visible holding market_value)`. Inconsistencies remain warnings.

Supported optional position analytics include:

- `cost_basis` / `total_cost` / `cost_basis_value`
- `average_cost` / `avg_cost` / `cost_per_share`
- `unrealized_pnl` / `unrealized_gain` / `unrealized_pl`
- `total_return_percent` / `total_return_pct` / `return_percent` / `return_pct`
- `daily_change_percent` / `daily_change_pct` / `day_change_percent` / `day_change_pct`
- `dividend_yield_percent` / `yield_percent` / `distribution_yield_percent`
- `annual_income` / `projected_annual_income` / `annual_dividend_income`
- `next_ex_dividend_date` / `next_ex_date` / `ex_dividend_date`

Missing values remain `Not reported`.

### 2026-08-07 — Holdings UI 2.0 grouped presentation and dual weights

The host now separates the former ultra-wide Holdings table into three professional strategy-scoped sections:

1. **Holdings Overview** — identity, sleeve, status, shares, price, market value, strategy allocation weight, and deployed-portfolio weight.
2. **Position Analytics** — cost basis, average cost, unrealized P/L, total return, and daily change.
3. **Income** — yield, projected annual income, next ex-dividend date, and evidence provenance.

The host now displays two distinct percentages for every holding when calculable:

- `% Strategy Allocation` = `holding.market_value / strategy.allocated_capital`.
- `% Deployed Portfolio` = `holding.market_value / sum(visible strategy holding market_value)`.

These values must not be conflated. The first shows how much of SWING-001's investor allocation the position consumes; the second shows composition of currently deployed SWING-001 holdings.

Additional presentation rules relevant to Swing:

- Missing optional analytics render as a neutral `Not reported` badge rather than a fabricated zero.
- Positive and negative performance values receive presentation-only gain/loss styling when authoritative values exist.
- Security names should be published through `name`, `security_name`, `display_name`, or `instrument_name` if Swing wants a professional named-instrument row.
- Swing does not need to publish logo/image assets for this host change.
- The Holdings CSS is host-owned and self-contained; Swing must not copy the styling layer.
- Reserve/cash holdings remain part of deployed-portfolio composition if explicitly published as a visible holding row.

### 2026-08-07 — Dividend Position Analytics evidence generation

The Dividend host now reconstructs open-paper position analytics from strategy-owned paper trade history and enriches current holdings before Enterprise publication. The current Dividend implementation uses buy/sell history to derive an active average-cost basis and may use the strategy's market-data snapshot for instrument identity and daily change.

The host may now receive these per-position fields from strategy evidence:

- `name` / `security_name` / `display_name` / `instrument_name`
- `cost_basis`
- `average_cost`
- `unrealized_pnl`
- `total_return_percent`
- `daily_change_percent`
- `analytics_source`

Dividend calculation rules introduced in this milestone:

- Open cost basis is reconstructed only from recorded paper buy evidence.
- A paper sell reduces the active cost basis proportionally using average cost; a full exit clears the old lot so a later re-entry starts a new cost basis.
- `unrealized_pnl = current market value - open cost basis` only when both values are authoritative.
- `total_return_percent = unrealized_pnl / cost_basis * 100` only when cost basis is positive.
- Daily change may be read directly from authoritative market evidence or derived from current price and previous close when both are present.
- Reserve/cash rows are not assigned fabricated trade cost-basis analytics.
- Missing trade or market evidence remains `Not reported`.

Swing compatibility requirement:

- Swing does **not** need to reproduce the Dividend trade-log reconstruction algorithm.
- SWING-001 should publish its own authoritative position analytics from Swing-owned lifecycle/performance artifacts whenever those values exist.
- Preferred semantic fields are `cost_basis`, `average_cost`, `unrealized_pnl`, `total_return_percent`, and `daily_change_percent`; the existing aliases remain accepted by the host renderer.
- Include a strategy-owned provenance field such as `analytics_source` or an equivalent evidence path so the Enterprise host can explain where the metric came from.
- A closed Swing position must not leak stale cost basis or unrealized P/L into a later re-entry.
- Missing Swing analytics must remain missing rather than defaulting to zero.

Potential Swing sources include `main/results/position_lifecycle.json`, `main/results/stock_performance_report.json`, and market-data evidence once the declared paths are available.

### 2026-08-07 — Watchlist detail

The Enterprise host supports both `watchlist_count` and structured `watchlist` rows. Swing should continue publishing authoritative Swing watchlist evidence with symbol/status and may preserve rank, score, committee decision, market-data state, or source.

Known readable Swing path: `main/results/watchlist_report.json`.

### 2026-08-07 — Performance detail contract

Where authoritative Swing evidence exists, publish or make discoverable trade counts, wins/losses/flats, win rate, open/closed trades, realized gain, and unrealized gain.

Known declared Swing evidence includes:

- `main/results/stock_performance_report.json`
- `main/results/weekly_stock_report.json`
- `main/results/monthly_command_center.json`

### 2026-08-07 — Alerts and risk flags

The host accepts strategy-scoped `alerts` and `risk_flags`. Swing should publish structured lifecycle, earnings, market-data, portfolio-risk, or governance warnings when authoritative and must not convert missing evidence into a false all-clear.

Potential sources include:

- `main/results/portfolio_risk.json`
- `main/results/position_lifecycle.json`
- `main/results/market_data_refresh_status.json`
- `main/results/swing_daily_cycle_report.json`

### 2026-08-07 — Decision Journal

The Enterprise host has a dedicated Decision Journal renderer and rejects cross-strategy journals. A Swing journal must use `strategy_id = SWING-001` and preserve paper-only/read-only safety rules.

## Current known Swing runtime gaps observed by the Enterprise host

The host has recently reported these SWING-001 declared artifacts as missing:

- `main/results/market_data_refresh_status.json`
- `main/results/monthly_command_center.json`
- `main/results/opportunity_quality_report.json`
- `main/results/portfolio_risk.json`
- `main/results/position_lifecycle.json`
- `main/results/stock_performance_report.json`
- `main/results/swing_daily_cycle_report.json`
- `main/results/weekly_stock_report.json`

These should not be manually copied into the Dividend repository. Swing should generate them at its declared canonical paths or update its Enterprise registration to the actual paths relative to the Swing repository.

## UI 2.0 compatibility principle

The professional UI is host-owned. Swing does not duplicate CSS or HTML. For each UI 2.0 step, Swing only needs to ensure its published Enterprise evidence supplies the same semantic contract.

## Next updates to this tracker

As UI 2.0 development continues, append Swing compatibility notes for:

1. Portfolio summary and attribution.
2. Professional Watchlist table.
3. Income/cash-flow presentation where applicable to Swing.
4. Detailed Performance dashboard.
5. Alerts and risk presentation.
6. Decision Journal presentation.
7. Any new Enterprise contract or schema field introduced by the host.

## Handoff rule

When the Dividend-side UI/evidence work is complete, this file should be provided to the Swing Bot development chat as the authoritative compatibility checklist. Swing changes should be implemented only in the Swing repository, while host rendering and aggregation changes remain in the Dividend repository.
