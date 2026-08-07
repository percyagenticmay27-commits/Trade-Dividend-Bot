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
- `projected_annual_income`
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

The host separates Holdings into three strategy-scoped sections: Holdings Overview, Position Analytics, and Income. The host displays `% Strategy Allocation` and `% Deployed Portfolio` as distinct metrics. Missing optional analytics render as neutral `Not reported` values rather than fabricated zeroes. Swing does not duplicate the host CSS or HTML.

### 2026-08-07 — Dividend Position Analytics evidence generation

The Dividend host reconstructs open-paper position analytics from strategy-owned paper trade history and enriches current holdings before Enterprise publication. Supported per-position fields include security name aliases, `cost_basis`, `average_cost`, `unrealized_pnl`, `total_return_percent`, `daily_change_percent`, and provenance.

Swing compatibility requirement:

- Swing does not reproduce the Dividend trade-log reconstruction algorithm.
- SWING-001 should publish its own authoritative position analytics from Swing-owned lifecycle/performance artifacts.
- A closed Swing position must not leak stale cost basis or unrealized P/L into a later re-entry.
- Missing Swing analytics must remain missing rather than defaulting to zero.

Potential Swing sources include `main/results/position_lifecycle.json`, `main/results/stock_performance_report.json`, and market-data evidence once declared paths are available.

### 2026-08-07 — Enterprise investor holdings consumer normalized to strategy KPIs

The legacy Enterprise Investor Dashboard allocation/holdings section previously depended on a separate reconstructed investor payload that could produce `UNKNOWN`, `$0.00`, and `Unclassified` rows even when normalized strategy holdings were already available. The host now prefers a read-only projection of the normalized `strategy_kpis[].holdings` evidence for this Enterprise-wide holdings table.

Host behavior:

- Only holdings with a real symbol and numeric market value are published into the Enterprise allocation view.
- Missing/invalid rows are skipped rather than converted into `UNKNOWN/$0` placeholders.
- Each row preserves its originating `strategy_id` and strategy display name.
- Enterprise allocation percentage is calculated only for presentation as `holding.market_value / total visible Enterprise holding market value`.
- The projection is marked `source = NORMALIZED_STRATEGY_KPIS` and remains read-only.
- Existing strategy allocation values, capital state, execution state, and governance are not modified.

Swing compatibility requirement:

- Once SWING-001 publishes structured holdings into its normalized Enterprise KPI row, those positions will automatically participate in the Enterprise Investor Dashboard holdings table.
- Swing must publish a usable `symbol` and numeric `market_value` for each visible holding.
- Optional `sector`, `theme`, or `category` improves Enterprise classification; otherwise the host displays `Unclassified` without inventing a sector.
- Swing should not publish placeholder holdings such as `UNKNOWN` solely to satisfy a schema.
- Swing does not need a separate investor-holdings HTML implementation or a duplicate Enterprise allocation report for this UI path.

### 2026-08-07 — Dividend income analytics evidence generation

The Dividend host now enriches current strategy holdings with authoritative income-oriented evidence when it exists. The host can populate the Holdings Income section with:

- `dividend_yield_percent`
- `annual_income`
- `next_ex_dividend_date`
- `payment_frequency`
- `income_analytics_source`

The strategy-level evidence may also expose `projected_annual_income`, calculated only by summing per-position annual-income values that were actually reported or safely derived from an authoritative annual dividend/distribution rate and current paper shares.

Dividend evidence rules introduced in this milestone:

- Yield is accepted only from source fields whose names explicitly identify percent semantics. Ambiguous decimal fields such as a generic `dividendYield` are not silently multiplied by 100 or otherwise guessed.
- Annual income may be read directly from authoritative per-position annual-income evidence.
- When direct annual income is unavailable, the Dividend host may derive it as `annual_dividend_rate_per_share * current paper shares` only when both values are available.
- Next ex-dividend date is copied from authoritative strategy/market evidence; it is never forecast from payment frequency.
- SGOV/reserve rows are not assigned Dividend-strategy income analytics by this enrichment step.
- Missing income evidence remains `Not reported`.

Swing compatibility requirement:

- Swing does not need to implement Dividend-specific yield or ex-dividend logic when those concepts are not applicable to the Swing strategy.
- If a Swing-held instrument has authoritative distribution/income evidence and the Swing strategy chooses to publish it, use the same semantic fields so the host can render them automatically.
- For non-income Swing positions, omit these fields rather than publishing zeroes solely to satisfy the UI.
- Any published Swing income metric must remain `SWING-001` scoped and include Swing-owned provenance.

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

As UI 2.0 development continues, append Swing compatibility notes for Portfolio summary/attribution, Professional Watchlist, detailed Performance, Alerts/risk presentation, Decision Journal presentation, and any new Enterprise contract introduced by the host.

## Handoff rule

When the Dividend-side UI/evidence work is complete, this file should be provided to the Swing Bot development chat as the authoritative compatibility checklist. Swing changes should be implemented only in the Swing repository, while host rendering and aggregation changes remain in the Dividend repository.
