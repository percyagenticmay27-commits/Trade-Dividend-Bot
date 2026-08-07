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

The Holdings UI distinguishes Allocated Capital, Deployed Holdings, Invested Positions, explicit reserve/cash, and Available / Undeployed Cash. Supported optional position analytics include cost basis, average cost, unrealized P/L, total return, daily change, dividend yield, annual income, and next ex-dividend date. Missing values remain `Not reported`.

### 2026-08-07 — Holdings UI 2.0 grouped presentation and dual weights

The host separates Holdings into Holdings Overview, Position Analytics, and Income. `% Strategy Allocation` and `% Deployed Portfolio` are distinct metrics. Missing optional analytics render as neutral `Not reported` values rather than fabricated zeroes. Swing does not duplicate the host CSS or HTML.

### 2026-08-07 — Dividend Position Analytics evidence generation

The Dividend host reconstructs open-paper position analytics from strategy-owned paper trade history and enriches current holdings before Enterprise publication. Supported per-position fields include security name aliases, `cost_basis`, `average_cost`, `unrealized_pnl`, `total_return_percent`, `daily_change_percent`, and provenance.

Swing compatibility requirement:

- Swing does not reproduce the Dividend trade-log reconstruction algorithm.
- SWING-001 should publish its own authoritative position analytics from Swing-owned lifecycle/performance artifacts.
- A closed Swing position must not leak stale cost basis or unrealized P/L into a later re-entry.
- Missing Swing analytics must remain missing rather than defaulting to zero.

Potential Swing sources include `main/results/position_lifecycle.json`, `main/results/stock_performance_report.json`, and market-data evidence once declared paths are available.

### 2026-08-07 — Enterprise investor holdings consumer normalized to strategy KPIs

The legacy Enterprise Investor Dashboard allocation/holdings section now prefers a read-only projection of normalized `strategy_kpis[].holdings` evidence. Placeholder `UNKNOWN/$0` holdings are no longer fabricated when valid strategy holdings exist.

Swing compatibility requirement:

- Once SWING-001 publishes structured holdings into its normalized Enterprise KPI row, those positions automatically participate in the Enterprise Investor Dashboard holdings table.
- Publish a usable `symbol` and numeric `market_value` for each visible holding.
- Optional `sector`, `theme`, or `category` improves Enterprise classification.
- Swing does not need a separate investor-holdings HTML implementation.

### 2026-08-07 — Dividend income analytics evidence generation

The Dividend host enriches current strategy holdings with authoritative income-oriented evidence when it exists. The host can populate `dividend_yield_percent`, `annual_income`, `next_ex_dividend_date`, `payment_frequency`, and `income_analytics_source`. Strategy-level evidence may expose `projected_annual_income` by summing only reported or safely derived per-position annual-income values.

Dividend evidence rules:

- Ambiguous generic yield fields are not interpreted by downstream analytics.
- Annual income may be derived as an authoritative annual dividend/distribution rate per share multiplied by current paper shares.
- Next ex-dividend date is copied from authoritative evidence; it is never forecast from payment frequency.
- Reserve rows are not assigned Dividend-strategy income analytics by this enrichment step.
- Missing income evidence remains `Not reported`.

Swing compatibility requirement:

- Swing does not need Dividend-specific yield logic when it is not applicable.
- If a Swing-held instrument has authoritative distribution/income evidence, publish the same semantic fields for automatic host rendering.
- Omit non-applicable fields rather than publishing zero solely to satisfy the UI.

### 2026-08-07 — Provider-normalized income market evidence

Production validation showed the Income renderer and analytics were working but the existing `market_data_snapshot.json` did not expose explicit income semantics. The host market-data boundary now normalizes provider-known fields before downstream strategy analytics consume them.

Dividend host behavior:

- Yahoo `dividend_yield` is treated at the provider/integration boundary as a decimal ratio and is published separately as explicit `dividend_yield_percent`; downstream strategy code still does not guess generic yield semantics.
- Provider `dividend_rate` is exposed as `annual_dividend_rate` so annual income can be derived from current paper shares.
- Provider security identity is exposed as `name` when available.
- Provider ex-dividend date is normalized to `next_ex_dividend_date` when reported. The host does not manufacture a future ex-date.
- Missing provider fields remain absent rather than becoming fabricated zeroes.
- Existing raw quote/history/dividend evidence remains preserved in the market snapshot for provenance.

Swing compatibility requirement:

- SWING-001 may publish already-normalized percent/rate/date fields from its own market-data layer and does not need to reproduce Yahoo-specific conversion logic.
- Prefer explicit semantic names such as `dividend_yield_percent`, `annual_dividend_rate`, `next_ex_dividend_date`, and `name` when those values are applicable and authoritative.
- If Swing consumes a provider whose yield units differ, normalization belongs at the Swing provider boundary, not in the Enterprise UI.
- Do not publish an ex-dividend date as "next" unless the source actually reports that date; stale or historical dates should retain their actual semantics.

### 2026-08-07 — Watchlist detail

The Enterprise host supports both `watchlist_count` and structured `watchlist` rows. Swing should continue publishing authoritative Swing watchlist evidence with symbol/status and may preserve rank, score, committee decision, market-data state, or source.

Known readable Swing path: `main/results/watchlist_report.json`.

### 2026-08-07 — Performance detail contract

Where authoritative Swing evidence exists, publish or make discoverable trade counts, wins/losses/flats, win rate, open/closed trades, realized gain, and unrealized gain.

Known declared Swing evidence includes `main/results/stock_performance_report.json`, `main/results/weekly_stock_report.json`, and `main/results/monthly_command_center.json`.

### 2026-08-07 — Alerts and risk flags

The host accepts strategy-scoped `alerts` and `risk_flags`. Swing should publish structured lifecycle, earnings, market-data, portfolio-risk, or governance warnings when authoritative and must not convert missing evidence into a false all-clear.

Potential sources include `main/results/portfolio_risk.json`, `main/results/position_lifecycle.json`, `main/results/market_data_refresh_status.json`, and `main/results/swing_daily_cycle_report.json`.

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
