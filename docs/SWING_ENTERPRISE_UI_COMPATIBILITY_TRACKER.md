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
- Enterprise aggregate dashboards are host-owned outputs and must never be republished as inline strategy evidence.

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

The market-data boundary exposes security identity and provider income fields when available. Production validation demonstrated that provider yield-unit assumptions must not be hard-coded downstream: values returned by the deployed Yahoo/yfinance path were already expressed in percent-like units for several ETFs, so blindly multiplying them by 100 produced invalid values such as 6871% and 13879%.

Permanent rule:

- Do not infer provider yield units merely from the generic field name `dividend_yield`.
- Preserve raw provider evidence for provenance.
- Prefer semantically explicit fields or a calculation whose units are independently known.
- Provider ex-dividend dates remain optional; do not manufacture a future date when the provider does not report one.

Swing compatibility requirement:

- If Swing consumes provider yield fields, establish and test the provider's actual unit contract before publishing `dividend_yield_percent`.
- Provider-specific normalization belongs in the Swing market-data layer, never in the Enterprise renderer.

### 2026-08-07 — Observed trailing-distribution income fallback

Production evidence showed that the current ETF provider frequently supplies neither `annual_dividend_rate` nor a future ex-dividend date. The Dividend income layer now prefers the already-fetched distribution payment history because those payments have unambiguous dollar-per-share semantics.

Dividend host behavior:

- Sum positive distribution payments observed during the trailing 365 days, anchored to the latest market-history date, to produce `trailing_12m_distribution_rate`.
- Derive `dividend_yield_percent` as `trailing_12m_distribution_rate / current_price * 100`.
- Derive per-position `annual_income` as `trailing_12m_distribution_rate * current paper shares` when no explicit annual-income value is available.
- Publish `trailing_12m_payment_count` and an observed frequency label such as `WEEKLY_OBSERVED`, `MONTHLY_OBSERVED`, or `QUARTERLY_OBSERVED`.
- Prefer this observed-payment calculation over ambiguous provider yield fields.
- Continue leaving `next_ex_dividend_date` missing unless a source actually reports a future ex-dividend date.
- SGOV/reserve remains excluded from Dividend-strategy income analytics.

Swing compatibility requirement:

- Swing does not need to reproduce this Dividend-specific fallback.
- If SWING-001 chooses to publish income for an instrument, it may use its own authoritative observed-distribution history and should preserve calculation provenance.
- Never turn a historical payment cadence into a claimed future ex-dividend date.

### 2026-08-07 — Yearly Distribution Yield naming and audit evidence

The host Income table now uses the clearer investor-facing label **Yearly Distribution Yield** instead of the generic `Yield`. For Dividend holdings, this metric represents the observed trailing-365-day cash distributions per share divided by the current market price when sufficient payment history exists. The legacy `dividend_yield_percent` field is retained for backwards compatibility, while `yearly_distribution_yield_percent` is the preferred explicit UI semantic.

Dividend audit fields now include:

- `yearly_distribution_yield_percent`
- `trailing_12m_distribution_rate`
- `trailing_12m_payment_count`
- `trailing_12m_window_start`
- `trailing_12m_window_end`
- `trailing_12m_first_payment_date`
- `trailing_12m_last_payment_date`
- `yearly_distribution_yield_price`
- `yearly_distribution_yield_method`
- `dividend_yield_source`
- `annual_income_share_count`
- `annual_income_method`
- `income_analytics_source`

The host renderer exposes a compact `Audit` disclosure for each Income row so a high distribution yield can be reproduced from its underlying rate, payment count, price, observation window, and method instead of being trusted as an unexplained percentage.

Swing compatibility requirement:

- If SWING-001 publishes an income/distribution yield, prefer the explicit semantic field `yearly_distribution_yield_percent` when it represents a trailing observed distribution yield.
- Preserve the price, observation window, payment count, calculation method, and evidence source used to derive the value.
- Do not label SEC yield, forward yield, option-income distribution rate, or another materially different metric as `yearly_distribution_yield_percent` unless the field contract genuinely matches the trailing observed-distribution calculation.
- The host continues accepting `dividend_yield_percent` for compatibility, but Swing should avoid ambiguous yield names in new evidence.

### 2026-08-07 — Bounded Registry evidence and recursive-dashboard protection

Production refreshes were OOM-killed after three Enterprise output files grew to approximately 1.6 GB each. Root cause: DIVIDEND-001 declares host-owned Enterprise dashboards (`ai_cio_executive_dashboard.json` and `enterprise_investor_dashboard.json`) as Registry artifacts. The Registry evidence loader previously inlined those complete dashboard payloads; the next refresh then embedded Registry evidence back into the same Enterprise dashboards, causing recursive/exponential file growth and multi-gigabyte memory use.

Permanent host rule:

- Any Registry artifact with `scope = ENTERPRISE` is availability/provenance metadata only. Its full payload is never inlined into per-strategy Registry evidence.
- Strategy-scoped artifacts remain inline when reasonably sized.
- Artifacts larger than the host inline-size ceiling are also metadata-only so refresh memory stays bounded.
- `available = true` still means the artifact exists and may be referenced; metadata-only does not mean missing.
- Host aggregate dashboards must not become strategy-owned evidence payloads.

Swing compatibility requirement:

- SWING-001 should declare its own artifacts as `scope = STRATEGY` unless the artifact is genuinely an Enterprise host aggregate.
- Do not declare host-generated `ai_cio_executive_dashboard.json`, `enterprise_investor_dashboard.json`, or other Enterprise aggregate outputs as Swing strategy evidence.
- Large Swing reports may remain independently readable by path/provenance even when the host keeps them metadata-only instead of embedding them.

### 2026-08-07 — Professional Watchlist UI 2.0 contract

The Enterprise host now has a dedicated professional Watchlist renderer with strategy-scoped summary cards, ranked candidate rows, explicit market-data freshness, held/not-held state, evidence provenance, and optional score columns. A reported watchlist count of zero is treated as a valid strategy state and is rendered as an explicit empty state rather than as missing data.

Supported structured Watchlist row fields include:

- `rank` / `watchlist_rank` / `candidate_rank`
- `symbol` / `candidate_id`
- `name` / `security_name` / `display_name` / `instrument_name`
- `status` / `watchlist_status` / `candidate_status`
- `opportunity_quality` / `opportunity_score` / `score`
- `conviction_score`
- `momentum_score`
- `daily_change_percent`
- `market_data_stale`
- `currently_held`
- `sources` / `source`

Permanent host behavior:

- Missing scores remain `Not reported`; the host does not invent neutral or zero scores.
- `market_data_stale = false` renders as fresh evidence; `true` renders as stale evidence.
- The Enterprise renderer never promotes, removes, ranks, buys, or allocates a candidate. It only displays strategy-published evidence.
- `watchlist_count = 0` with an empty list is not an error.

Swing compatibility requirement:

- SWING-001 should publish its authoritative watchlist rows as structured evidence rather than only a count.
- Preserve the Swing-owned rank, committee or lifecycle status, opportunity/conviction/momentum scores, market-data freshness, held state, and evidence source when those fields exist.
- Do not fabricate a score merely so a host column is populated.
- Known readable Swing path remains `main/results/watchlist_report.json`.

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

As UI 2.0 development continues, append Swing compatibility notes for Portfolio summary/attribution, detailed Performance, Alerts/risk presentation, Decision Journal presentation, and any new Enterprise contract introduced by the host.

## Handoff rule

When the Dividend-side UI/evidence work is complete, this file should be provided to the Swing Bot development chat as the authoritative compatibility checklist. Swing changes should be implemented only in the Swing repository, while host rendering and aggregation changes remain in the Dividend repository.


### 2026-08-15 — Swing Trade Analytics / Position Performance consumer

The Enterprise host now renders a SWING-001-specific Trade Analytics section in place of the Dividend-oriented Income presentation. DIVIDEND-001 continues using the existing Income renderer without a contract or layout change.

Architecture decision:

- Discovery remains Registry v2 driven. SWING-001 must declare capability `trade_analytics` and the authoritative `trade_analytics` JSON artifact.
- Relative artifact paths resolve beneath the strategy registration's `repository_root`; paths that escape that root are rejected.
- The preferred source is the dedicated registered `results/swing_trade_analytics_report.json`.
- The `trade_analytics` section of registered `enterprise_strategy_kpis.json` remains a backward-compatible fallback.
- Generated Swing results are never copied into or edited inside Trade-Dividend-Bot.
- The host displays authoritative open and authentic closed rows only. A count never creates a position.
- Open rows do not display exit/sale fields.
- Closed-position columns render only when authentic `closed_positions` evidence is present.
- Missing optional evidence displays `Unavailable`; it is not inferred.
- Maximum drawdown is consumed only under policy `AUTHORITATIVE_POSITION_HISTORY_ONLY`, with `max_drawdown_inference_allowed = false`.
- Profit values render green and loss values render red.
- Strategy-owned text is HTML escaped.
- The presentation remains paper-only and read-only. It does not place orders, connect to a broker, move capital, or change allocations.

Current validated evidence expectation:

- SWING-001 allocation remains $4,500.
- DIVIDEND-001 allocation remains $5,000.
- Current authentic Swing ledger contains two open positions (SOXL and TQQQ) and zero closed positions.
- SOXL authoritative maximum drawdown is $82.42 / 7.308378%.
- TQQQ authoritative maximum drawdown is $25.17 / 3.728951%.

Continuation point:

- Pull branch `feature/dashboard-refresh-discovery-summary`.
- Run focused tests for `enterprise_strategy_kpi_adapter`, `enterprise_trade_analytics_ui`, and `enterprise_portal_trade_analytics_integration`.
- Then run the complete relevant Enterprise portal suite.
- Refresh Registry and Enterprise dashboards only after tests pass.


## 2026-08-15 full Enterprise regression reconciliation

The complete relevant Enterprise suite exposed five assertions after the Swing Trade Analytics consumer was added.

Decisions:

- Dividend realized income remains transaction-ledger authoritative. When normalized `net_income_received` is available, it overrides the paper-state cumulative compatibility total in the Enterprise KPI row.
- Dividend Watchlist retains and displays its published evidence source as well as the evidence timestamp.
- SWING-001 no longer receives a Dividend Income renderer, including when optional Trade Analytics evidence is unavailable. It receives an explicit non-fabricating Trade Analytics unavailable state.
- Holdings reconciliation no longer promises an obsolete checkmark label.
- Position history presents the human-readable `Why Sold` explanation while retaining the audit source; raw exit codes are not required as user-facing text.

No Swing repository files or generated result artifacts were modified.


## 2026-08-15 Swing Holdings deep-link correction

Visual validation showed that `?strategy=SWING-001&tab=holdings` still contained the shared Holdings renderer's Dividend-oriented Income subsection. The initial Trade Analytics integration had replaced only the former Income tab.

Decision:

- SWING-001 Holdings preserves capital reconciliation, holdings overview, position analytics, and position management.
- SWING-001 Holdings omits the Dividend distribution-income subsection.
- The authoritative Trade Analytics / Position Performance renderer is appended to the Swing Holdings route because Holdings is a common direct link.
- The former Income tab remains a backward-compatible route labeled Trade Analytics.
- DIVIDEND-001 Holdings and Income remain unchanged.
- No host-side drawdown calculation, exit fabrication, or Swing repository mutation is permitted.


## 2026-08-15 Swing authoritative Alerts consumer

The Enterprise host now consumes the registered SWING-001 Alerts report and renders it through a Swing-specific Alerts presentation. DIVIDEND-001 continues using the existing Dividend Alerts path unchanged.

Architecture decision:

- Discovery remains Registry v2 driven. SWING-001 must declare capability `alerts` and the strategy-scoped `swing_strategy_alerts_report` artifact.
- Relative artifact paths resolve beneath the registered external strategy `repository_root`; external evidence is never copied into Dividend results.
- The dedicated registered report is authoritative and takes precedence over embedded compatibility evidence.
- `dashboard_sections.alerts` in the registered Swing KPI artifact is a backward-compatible fallback only when the dedicated report is unavailable.
- The internal Swing fallback remains eligible only when external registered evidence is genuinely unavailable.
- The host accepts only policy `CURRENT_AUTHORITATIVE_EVIDENCE_ONLY` with `paper_trade_mode = true` and `advisory_only = true`.
- Actionable rows are displayed exactly as published. The host does not infer severity, priority, recommended action, or alert state.
- A verified zero-actionable-alert report displays the authoritative Swing all-clear message.
- `evidence_warnings` render separately as **Evidence Disclosures** and never become trade alerts.
- Legacy risk flags rejected by Swing authority are not revived by the host Alerts renderer.
- Missing or invalid optional evidence remains visibly unavailable and does not generate an all-clear.
- Strategy-owned text is HTML escaped.
- SWING-001 allocation remains $4,500 and DIVIDEND-001 remains $5,000.
- The consumer is read-only, paper-only, advisory-only, and cannot place orders, execute through a broker, move capital, or enable Robinhood execution.
- No Trade-Swing-Bot source or generated result was modified.

Continuation point:

- Pull `feature/dashboard-refresh-discovery-summary`.
- Run the focused Swing Alerts UI, adapter, workspace integration, and portal-route regressions.
- Refresh Registry and Enterprise dashboards only after the tests pass.
- Restart `dividend-allocation.service` and validate the SWING-001 Alerts deep link.


## 2026-08-15 Swing authoritative Decision Journal consumer

The Enterprise host now consumes the registered SWING-001 Decision Journal and replaces the Dividend pair-lifecycle presentation with a Swing-specific stock, position, and candidate lifecycle view. DIVIDEND-001 remains unchanged.

Architecture decision:

- Registry v2 capability `decision_journal` gates the consumer.
- The dedicated registered `results/swing_decision_journal_report.json` is preferred regardless of declared artifact loading order.
- `dashboard_sections.decisions` in the registered Swing Enterprise KPI is the contract-compatible fallback.
- Relative paths resolve beneath the external strategy's registered `repository_root`; path containment remains enforced.
- The consumer accepts only `CURRENT_MATCHED_AUTHORITATIVE_EVIDENCE_ONLY` reports that remain paper-only and advisory-only.
- `position_decisions` and `candidate_decisions` are consumed separately; the host does not derive category membership from counts or from the combined list.
- Open-position cards display symbol, scope, state, decision, owner, rationale, alternatives, timestamp, and committee timeline.
- Candidate cards use the same evidence fields but remain visually and structurally separate.
- Evidence warnings render separately as **Evidence Disclosures**.
- A verified empty report displays the Swing-published no-decisions message.
- Missing, stale, unsafe, or cross-strategy evidence remains unavailable without fabrication.
- Decisions outside the registered advisory set fail closed. The host does not manufacture BUY, SELL, sale, exit, or closure evidence.
- `rebalance_actions.json` remains a planning source and is never consumed as an executed Decision Journal source.
- No Dividend pair, income-leg, or leverage-leg terminology appears in the SWING-001 view.
- SWING-001 remains allocated $4,500 and all paper-only safety locks remain intact.
- No Trade-Swing-Bot file or generated artifact was modified.

Continuation point:

- Pull `feature/dashboard-refresh-discovery-summary`.
- Run the focused adapter, Swing Decision Journal UI, workspace integration, and portal-route tests.
- Refresh Registry and Enterprise dashboards after tests pass.
- Restart only `dividend-allocation.service`.
- Validate `/executive-dashboard?strategy=SWING-001&tab=decisions`.
