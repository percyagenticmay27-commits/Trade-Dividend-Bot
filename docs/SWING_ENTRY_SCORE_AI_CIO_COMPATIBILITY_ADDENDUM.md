# Swing Entry Score / AI CIO Compatibility Addendum

## Purpose

This addendum records the Enterprise-facing consequences of the Dividend Entry Score development. It is a compatibility handoff for the Swing Bot development chat. The Dividend repository remains the Enterprise AI CIO host; nothing here authorizes changing the Swing repository from the Dividend repository.

## Dividend-side Strategy A / Strategy B timing model

DIVIDEND-001 now publishes two distinct strategy-owned timing models from already-fetched daily OHLC evidence.

### Strategy A — Oscillator / Momentum

The arming mechanism uses:

- Stochastic Oscillator `(14,3,3)` where `%K > %D` and `%K >= 50`, **or**
- RSI(14) at or above `50`.

A fresh RSI cross is retained as audit evidence, but RSI does not have to cross 50 again every day. While RSI remains in the 50–100 regime, Strategy A remains allowed to use its Stochastic RSI lever.

Once armed, the execution lever is Stochastic RSI `(14,7,3,3)`.

A Strategy A BUY-active state requires the arming mechanism above and Stochastic RSI `%K > %D`. A fresh Stochastic RSI `%K/%D` crossover is not required on every BUY evaluation. Rising `%K`, a fresh K-over-D crossover, and K entering 50 or 80 remain audit/supporting evidence rather than repeated mandatory prerequisites.

A Strategy A SELL trigger occurs when either Stochastic RSI `%D` genuinely crosses above `%K` or Stochastic Oscillator `%D` genuinely crosses above `%K`. Touching/equality alone is not a SELL crossover.

### Strategy B — EMA Trend

A Strategy B BUY-eligible state requires `Price > EMA20 > EMA50`. A Strategy B SELL trigger occurs when current Price is below EMA20.

## Correction to the prior Fast Stochastic overextension draft

The prior temporary Dividend rule that treated raw Fast Stochastic `%K >= 90` as an automatic overextension blocker has been retired. It conflicted with the approved Strategy A design. The old raw Fast Stochastic 14-period value remains available only as audit/backward-compatibility evidence and is explicitly marked `entry_authority = false`.

The authoritative Dividend oscillator evidence is now Stochastic Oscillator `(14,3,3)`, RSI(14), and Stochastic RSI `(14,7,3,3)`.

## Strategy ownership and lifecycle routing

DIVIDEND-001 has a dedicated strategy-ownership router and the qualified-entry paper wrapper persists the resolved methodology into `paper_state.json` when an ETF position actually opens or re-opens.

Permanent ownership rules:

- an existing open position keeps its valid strategy owner for the life of that open cycle;
- if only Strategy A is BUY-active for a new position, Strategy A may own that position;
- if only Strategy B is BUY-active for a new position, Strategy B may own that position;
- if neither strategy is BUY-active, entry waits with `NO_ACTIVE_ENTRY_STRATEGY`;
- if both strategies are BUY-active and no explicit precedence/selection policy exists, the router fails closed with `MULTIPLE_ACTIVE_ENTRY_STRATEGIES_REQUIRE_SELECTION_POLICY`;
- an A-owned position ignores Strategy B SELL triggers;
- a B-owned position ignores Strategy A SELL triggers;
- unknown ownership cannot generate a strategy-routed SELL.

### Persisted Dividend paper-state fields

For a pair-managed qualified entry, the paper state can persist `strategy_owner`, `a_strategy_owner`, `b_strategy_owner`, and `strategy_ownership_source = QUALIFIED_ENTRY_GATE`. For independent sleeves the equivalent owner/source fields are persisted independently for A and B. Failed or waiting entries do not fabricate ownership.

### Owner-controlled SELL routing

The daily Dividend paper loop reads the persisted owner before an ordinary technical exit is allowed.

- `STRATEGY_A` ownership routes SELL authority only through Strategy A's current `strategy_signals.strategy_a.sell_trigger` evidence.
- `STRATEGY_B` ownership routes SELL authority only through Strategy B's current `strategy_signals.strategy_b.sell_trigger` evidence.
- A SELL emitted by the non-owning strategy is ignored.
- Missing/unknown ownership fails closed for strategy-routed exits; it does not fall back to a legacy technical SELL.
- Legacy aggregate signals remain report/audit context and no longer own ordinary technical exits when the Strategy A/B lifecycle is in use.
- Scheduled pre-earnings exits remain a separate risk/governance override and can close a position regardless of Strategy A/B ownership.
- Post-earnings re-entry still passes through the qualified entry gate and receives a newly persisted owner only if the position actually re-opens.

When an owner-controlled exit closes a position, current ownership is cleared and the paper state preserves `last_exit_strategy_owner` plus the owner-specific exit reason codes. Independent sleeves preserve the equivalent side-specific last-exit owner/reason fields.

## Enterprise / AI CIO ownership evidence

The Dividend dashboard evidence layer now normalizes persisted ownership into Enterprise-facing fields instead of requiring the AI CIO UI to inspect raw paper state.

Current holdings can publish:

- `strategy_owner`;
- `entry_method`;
- `strategy_ownership_source`.

Completed lifecycle rows can publish:

- `entry_method`;
- `last_exit_strategy_owner`;
- `exit_method`;
- `last_exit_strategy_reasons`;
- `last_exit_reason`;
- `strategy_exit_evidence_source`.

For a normal owner-controlled lifecycle, `entry_method` and `exit_method` identify the strategy methodology that owned that completed position. Risk/governance overrides remain separately attributable in the preserved reason evidence.

The Enterprise Position / Sales History UI now has explicit columns for **Entry Method**, **Exit Method**, and **Exit Reason**. Missing ownership evidence is rendered as `Not reported`; the host must not infer or fabricate a methodology.

These fields flow through the existing DIVIDEND-001 dashboard-detail → Enterprise KPI path, so `enterprise_strategy_kpis.json` can expose the same ownership/lifecycle evidence to jshouseapi.com without changing the Swing repository.

## Enterprise evidence fields

Dividend symbol-specific Entry Score evidence can include `strategy_signals`, strategy ownership, owner-specific SELL authority, exact reason codes, prior/current crossover evidence, market-data freshness, and provenance. Missing or insufficient market evidence remains fail-closed.

## Entry status contract

The Enterprise host can continue consuming `STRONG_ENTRY`, `GOOD_ENTRY`, `WATCH`, `WAIT`, `AVOID`, and `UNKNOWN`. Opportunity Quality and Entry Timing remain separate. High Opportunity Quality does not authorize an entry by itself.

## AI CIO implications

The AI CIO should be able to explain which Dividend timing strategy is active, which strategy owns an open position, why an entry is waiting, and exactly which owning strategy caused an exit. Examples include `Strategy A SELL caused by STOCH_RSI_D_CROSSED_ABOVE_K`, `Strategy B SELL because PRICE_BELOW_EMA20`, and `Existing position remains owned by STRATEGY_A despite a Strategy B signal`.

The Enterprise host must display supplied strategy evidence; it must not recompute Dividend or Swing trading logic.

## Swing compatibility requirement

SWING-001 must not copy Dividend's Strategy A or Strategy B formulas unless Swing independently chooses those rules for its own strategy.

If Swing supports multiple entry methodologies, Swing should persist the method that actually owns an open paper position in Swing's own authoritative lifecycle/state. Its ordinary technical exit router should then consult that persisted owner and only honor that owner's exit methodology. A signal from another Swing method must not silently close the position unless Swing explicitly documents an override/migration policy.

Swing should also distinguish normal strategy exits from independent governance/risk exits. If Swing has earnings exits, portfolio-risk exits, hard safety exits, or another governance override, those should be labeled separately rather than presented as if the owning entry methodology generated the SELL.

For AI CIO interoperability, Swing should publish equivalent semantic ownership fields in its own canonical Enterprise artifact where applicable:

- current `strategy_owner` / method owner;
- `entry_method`;
- ownership source/provenance;
- latest `exit_method` or last-exit owner;
- machine-readable exit reason codes;
- a human-readable exit reason where available;
- evidence source/freshness;
- paper-only/broker-disabled flags.

The AI CIO may display those fields but must not become the system of record for Swing lifecycle ownership and must never manufacture missing Swing ownership values from Dividend conventions.

## Cross-strategy permanent rules

- Opportunity Quality answers whether an opportunity is attractive.
- Entry Timing answers whether capital should be deployed now.
- A WAIT must have an explicit reason whenever strategy evidence supports one.
- Missing/UNKNOWN evidence fails closed.
- SELL crossovers require prior/current evidence and cannot be inferred from lines merely touching.
- Open-position strategy ownership remains stable until that lifecycle is closed or explicitly migrated by a documented policy.
- Ordinary technical exits must route through the persisted owner.
- Independent risk/governance exits must remain separately attributable.
- Enterprise ownership fields are presentation/audit evidence; strategy state remains authoritative.
- Strategy calculations remain owned by their source strategy.
- The Enterprise AI CIO aggregates, governs, and displays; it does not silently replace strategy logic.

## Swing regression tests to add

Swing development should add tests proving that missing/stale entry evidence fails closed; candidate-specific evidence is not replaced by a global score; high Opportunity Quality cannot bypass failed Entry Timing; every WAIT has a reason; crossover exits distinguish a real cross from touching; ownership is persisted after a position opens; failed entries do not fabricate ownership; an open position's owning method alone controls ordinary technical exits; a different method's SELL is ignored; unknown ownership fails closed; governance/risk exits remain separately attributable; last-exit owner/reason is preserved where applicable; Enterprise KPI/display evidence preserves Swing-supplied ownership without recomputing it; missing ownership displays as missing rather than fabricated; cross-strategy evidence cannot be consumed as SWING-001 evidence; paper-only/no-order flags remain locked; and canonical Swing evidence reaches the Enterprise registry.

## Dividend files changed for this strategy timing / ownership milestone

- `src/dividend_bot/dividend_entry_strategy_signals.py`
- `src/dividend_bot/dividend_technical_entry_evidence.py`
- `src/dividend_bot/dividend_strategy_ownership.py`
- `src/dividend_bot/dividend_strategy_ownership_evidence.py`
- `src/dividend_bot/dividend_dashboard_evidence.py`
- `src/dividend_bot/enterprise_position_history_ui.py`
- `paper_trading_engine.py`
- `tests/test_dividend_entry_strategy_signals.py`
- `tests/test_dividend_entry_score_market_evidence.py`
- `tests/test_dividend_strategy_ownership.py`
- `tests/test_dividend_strategy_ownership_evidence.py`
- `tests/test_paper_trading_strategy_ownership_persistence.py`
- `tests/test_paper_trading_strategy_owner_exit_routing.py`
- `tests/test_enterprise_position_history_ui.py`

This addendum should be consolidated into `SWING_ENTERPRISE_UI_COMPATIBILITY_TRACKER.md` during the next documentation consolidation pass.
