# Swing Entry Score / AI CIO Compatibility Addendum

## Purpose

This addendum records the Enterprise-facing consequences of the Dividend Entry Score development. It is a compatibility handoff for the Swing Bot development chat. The Dividend repository remains the Enterprise AI CIO host; nothing here authorizes changing the Swing repository from the Dividend repository.

## Dividend-side Strategy A / Strategy B timing model

DIVIDEND-001 publishes two distinct strategy-owned timing models from already-fetched daily OHLC evidence.

### Strategy A — Oscillator / Momentum

Strategy A deliberately uses a slower momentum gate plus a faster execution lever.

The arming mechanism uses either:

- Stochastic Oscillator `(14,3,3)` where `%K > %D` and **both `%K` and `%D` are at or above 50**, or
- RSI(14) at or above `50`.

A fresh RSI cross is retained as audit evidence, but RSI does not have to cross 50 again every day. While RSI remains in the 50–100 regime, Strategy A remains allowed to use its Stochastic RSI lever.

Once armed, the execution lever is Stochastic RSI `(14,7,3,3)`.

A Strategy A BUY-active state requires:

- the slower arming mechanism above;
- Stochastic RSI `%K > %D`; and
- Stochastic RSI `%K` rising versus the prior daily value.

A fresh Stochastic RSI `%K/%D` crossover is not required on every BUY evaluation. A prior crossover and K entering 50 or 80 remain supporting/audit evidence.

### Strategy A buffered exit architecture

Stochastic RSI is intentionally faster than the Stochastic Oscillator. Therefore a Stochastic RSI bearish crossover is treated as an **early exit warning**, not automatic SELL authority.

The stages are:

1. `STOCH_RSI_D_CROSSED_ABOVE_K` → `exit_warning_active = true`.
2. If the slower Stochastic Oscillator has not confirmed deterioration, the position remains HOLD and the warning is buffered.
3. A normal Strategy A SELL is confirmed only when Stochastic Oscillator `%D` genuinely crosses above `%K` **and both oscillator lines are below 80**.
4. A Stochastic Oscillator bearish crossover while either line remains at or above 80 is buffered and does not force an exit.
5. Equality/touching alone is never treated as a crossover.

This creates three explicit owner-routed exit states for Strategy A:

- `HOLD`
- `WARNING_BUFFERED`
- `SELL_CONFIRMED`

The owner router preserves the warning fields even when `sell_trigger = false`, allowing the paper lifecycle and AI CIO to distinguish a fast momentum warning from a confirmed strategy exit.

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

- `STRATEGY_A` ownership routes SELL authority only through Strategy A's current buffered exit evidence.
- `STRATEGY_B` ownership routes SELL authority only through Strategy B's current `strategy_signals.strategy_b.sell_trigger` evidence.
- A SELL emitted by the non-owning strategy is ignored.
- Missing/unknown ownership fails closed for strategy-routed exits; it does not fall back to a legacy technical SELL.
- Strategy A warning evidence can be retained while the final `sell_trigger` remains false.
- Legacy aggregate signals remain report/audit context and no longer own ordinary technical exits when the Strategy A/B lifecycle is in use.
- Scheduled pre-earnings exits remain a separate risk/governance override and can close a position regardless of Strategy A/B ownership.
- Post-earnings re-entry still passes through the qualified entry gate and receives a newly persisted owner only if the position actually re-opens.

When an owner-controlled exit closes a position, current ownership is cleared and the paper state preserves `last_exit_strategy_owner` plus the owner-specific exit reason codes. Independent sleeves preserve the equivalent side-specific last-exit owner/reason fields.

## Legacy pre-ownership positions

Positions opened before the ownership fields were introduced can legitimately have `strategy_owner = null`. The Enterprise host must not rewrite those historical positions as Strategy A or Strategy B merely because one of those methods is active today.

Dividend includes a **read-only legacy ownership reconstruction audit**. It reconstructs Strategy A/B evidence at the current open cycle's original entry date using the shared historical market snapshot and the configured signal symbol. For pair-managed positions, the underlying signal symbol from `paper_portfolio_config.py` is used (for example AMD for AMDW/AMDL, NVDA for NVDW/NVDX, AVGO for AVGW/AVGX). The audit:

- never mutates `paper_state.json`;
- never moves capital;
- never places or simulates an order;
- only marks a position `ELIGIBLE_FOR_EXPLICIT_BACKFILL` when exactly one strategy would have been BUY-active at that historical entry date;
- keeps the position `KEEP_LEGACY_UNASSIGNED` when neither strategy, both strategies, missing history, or incomplete evidence prevents an unambiguous reconstruction.

The output is `results/legacy_strategy_ownership_audit.json`. Any future ownership backfill must be an explicit migration step after this evidence is reviewed; automatic retroactive ownership is prohibited.

Swing should apply the same semantic principle if it later introduces method ownership after legacy positions already exist: reconstruct historical method evidence read-only first, do not silently assign current methodology to old positions, and require explicit migration when historical evidence is unambiguous.

## Enterprise / AI CIO ownership evidence

The Dividend dashboard evidence layer normalizes persisted ownership into Enterprise-facing fields instead of requiring the AI CIO UI to inspect raw paper state.

Current holdings can publish `strategy_owner`, `entry_method`, and `strategy_ownership_source`. Completed lifecycle rows can publish `entry_method`, `last_exit_strategy_owner`, `exit_method`, `last_exit_strategy_reasons`, `last_exit_reason`, and `strategy_exit_evidence_source`.

Strategy A current-exit evidence now propagates from the already-calculated symbol-specific `entry_score_report.json` strategy signals through the owner router into current Dividend holdings. The dashboard does **not** recompute RSI, Stochastic Oscillator, or Stochastic RSI. For an owned current holding it can publish:

- `exit_state`
- `exit_warning_active`
- `exit_buffered`
- `exit_warning_reasons`
- `sell_trigger`
- `sell_reasons`
- `exit_authority_reason`
- `exit_evidence_source`

`exit_evidence_source = entry_score_report.json` identifies the current calculated signal artifact. If a position has a valid persisted owner but current symbol-specific strategy signal evidence is unavailable, the Enterprise layer publishes `exit_state = UNKNOWN`, `sell_trigger = false`, and `exit_authority_reason = CURRENT_STRATEGY_SIGNAL_EVIDENCE_UNAVAILABLE`. It must not infer an exit from stale ownership alone.

A Strategy A `WARNING_BUFFERED` holding remains `position_status = OPEN`; it is not converted to a completed sale or SGOV lifecycle event. `SELL_CONFIRMED` reports current owner exit authority but likewise does not fabricate a completed sale before the paper trading lifecycle actually records the close.

The Enterprise Position / Sales History UI has explicit columns for **Entry Method**, **Exit Method**, and **Exit Reason**. Missing ownership evidence remains missing; the host must not infer or fabricate a methodology.

These current holding fields flow through the existing DIVIDEND-001 dashboard-detail → Enterprise KPI path because `enterprise_strategy_kpi_adapter.py` passes the detailed Dividend `holdings` collection into `enterprise_strategy_kpis.json`. Therefore the AI CIO can consume the state without a second calculation engine.

## Enterprise evidence fields

Dividend symbol-specific Entry Score evidence can include `strategy_signals`, strategy ownership, owner-specific SELL authority, exact reason codes, prior/current crossover evidence, market-data freshness, and provenance. Missing or insufficient market evidence remains fail-closed.

## Entry status contract

The Enterprise host can continue consuming `STRONG_ENTRY`, `GOOD_ENTRY`, `WATCH`, `WAIT`, `AVOID`, and `UNKNOWN`. Opportunity Quality and Entry Timing remain separate. High Opportunity Quality does not authorize an entry by itself.

## AI CIO implications

The AI CIO should be able to explain which Dividend timing strategy is active, which strategy owns an open position, why an entry is waiting, whether a Strategy A fast exit warning is currently buffered, and exactly which owning strategy caused a confirmed exit. The Enterprise host must display supplied strategy evidence; it must not recompute Dividend or Swing trading logic.

## Swing compatibility requirement

SWING-001 must not copy Dividend's Strategy A or Strategy B formulas unless Swing independently chooses those rules for its own strategy.

If Swing supports multiple entry methodologies, Swing should persist the method that actually owns an open paper position in Swing's own authoritative lifecycle/state. Its ordinary technical exit router should then consult that persisted owner and only honor that owner's exit methodology. A signal from another Swing method must not silently close the position unless Swing explicitly documents an override/migration policy.

If Swing has a fast-warning/slow-confirmation architecture of its own, it should publish warning state separately from final exit authority. The Enterprise host should display that state but must not convert a warning into a SELL.

Swing should distinguish normal strategy exits from independent governance/risk exits. For AI CIO interoperability, Swing should publish equivalent semantic ownership fields in its own canonical Enterprise artifact where applicable: current method owner, entry method, ownership provenance, latest exit method/owner, machine-readable exit reasons, human-readable exit reason, warning/buffer state where applicable, freshness/provenance, and paper-only/broker-disabled flags.

If Swing has legacy open positions that predate method ownership, Swing should not assign ownership from current signals. It should reconstruct evidence as of the historical entry date where possible and require explicit migration for any retroactive owner assignment.

## Cross-strategy permanent rules

- Opportunity Quality answers whether an opportunity is attractive.
- Entry Timing answers whether capital should be deployed now.
- A WAIT must have an explicit reason whenever strategy evidence supports one.
- Missing/UNKNOWN evidence fails closed.
- SELL crossovers require prior/current evidence and cannot be inferred from lines merely touching.
- Fast warning evidence must remain distinct from confirmed exit authority.
- Open-position strategy ownership remains stable until that lifecycle is closed or explicitly migrated by a documented policy.
- Ordinary technical exits must route through the persisted owner.
- Independent risk/governance exits must remain separately attributable.
- Legacy ownership must not be retroactively fabricated from current signals.
- Enterprise ownership fields are presentation/audit evidence; strategy state remains authoritative.
- Strategy calculations remain owned by their source strategy.
- The Enterprise AI CIO aggregates, governs, and displays; it does not silently replace strategy logic.

## Swing regression tests to add

Swing development should test missing/stale evidence fail-closed behavior; candidate-specific Entry Timing; WAIT reasons; real crossover semantics; sticky method ownership; owner-only exits; separation of fast warning from confirmed exit where applicable; risk override attribution; last-exit owner/reason preservation; legacy-position historical reconstruction without automatic mutation; ambiguous legacy reconstruction remaining unassigned; Enterprise propagation without host-side recomputation; and paper-only/no-order locks.

## Dividend files changed for this strategy timing / ownership milestone

- `src/dividend_bot/dividend_entry_strategy_signals.py`
- `src/dividend_bot/dividend_technical_entry_evidence.py`
- `src/dividend_bot/dividend_strategy_ownership.py`
- `src/dividend_bot/dividend_strategy_ownership_evidence.py`
- `src/dividend_bot/dividend_legacy_strategy_ownership_audit.py`
- `src/dividend_bot/dividend_dashboard_evidence.py`
- `src/dividend_bot/enterprise_position_history_ui.py`
- `paper_trading_engine.py`
- `audit_legacy_strategy_ownership.py`
- related regression tests

This addendum should be consolidated into `SWING_ENTERPRISE_UI_COMPATIBILITY_TRACKER.md` during the next documentation consolidation pass.
