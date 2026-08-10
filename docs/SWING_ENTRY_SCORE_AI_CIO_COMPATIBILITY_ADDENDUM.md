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

A Strategy A BUY-active state requires:

- the arming mechanism above; and
- Stochastic RSI `%K > %D`.

A fresh Stochastic RSI `%K/%D` crossover is **not** required on every BUY evaluation. If the mechanism remains armed and `%K` is already above `%D`, the BUY lever remains active. Rising `%K`, a fresh K-over-D crossover, and K entering 50 or 80 are published as supporting audit evidence when they occur, but they are not mandatory repeated prerequisites.

A Strategy A SELL trigger occurs when either:

- Stochastic RSI `%D` genuinely crosses above `%K`; or
- Stochastic Oscillator `%D` genuinely crosses above `%K`.

Touching/equality by itself is not a SELL crossover. The implementation requires an actual side change between the previous and current observations.

### Strategy B — EMA Trend

A Strategy B BUY-eligible state requires:

- Price > EMA20; and
- EMA20 > EMA50.

Therefore the bullish structure is `Price > EMA20 > EMA50`.

A Strategy B SELL trigger occurs when current Price is below EMA20.

## Correction to the prior Fast Stochastic overextension draft

The prior temporary Dividend rule that treated raw Fast Stochastic `%K >= 90` as an automatic overextension blocker has been retired. It conflicted with the approved Strategy A design, where Stochastic RSI entering 80 can be part of the valid execution lever.

The old raw Fast Stochastic 14-period value remains available only as audit/backward-compatibility evidence and is explicitly marked `entry_authority = false`.

The authoritative Dividend oscillator evidence is now:

- Stochastic Oscillator `(14,3,3)`;
- RSI(14);
- Stochastic RSI `(14,7,3,3)`.

## Strategy ownership and lifecycle routing

DIVIDEND-001 now has a dedicated strategy-ownership router and the qualified-entry paper wrapper now persists the resolved methodology into `paper_state.json` when an ETF position actually opens or re-opens.

Permanent ownership rules:

- an existing open position keeps its valid strategy owner for the life of that open cycle;
- if only Strategy A is BUY-active for a new position, Strategy A may own that position;
- if only Strategy B is BUY-active for a new position, Strategy B may own that position;
- if neither strategy is BUY-active, entry waits with `NO_ACTIVE_ENTRY_STRATEGY`;
- if both strategies are BUY-active and no explicit precedence/selection policy exists, the router fails closed with `MULTIPLE_ACTIVE_ENTRY_STRATEGIES_REQUIRE_SELECTION_POLICY` rather than arbitrarily assigning ownership;
- an A-owned position must ignore Strategy B SELL triggers;
- a B-owned position must ignore Strategy A SELL triggers;
- unknown ownership cannot generate a strategy-routed SELL.

### Persisted Dividend paper-state fields

For a pair-managed qualified entry, the paper state can now persist:

- `strategy_owner`;
- `a_strategy_owner`;
- `b_strategy_owner`;
- `strategy_ownership_source = QUALIFIED_ENTRY_GATE`.

A pair-managed position receives one common owner only when the qualified entry gate supplies one unambiguous strategy owner. Multiple owners are not collapsed into an invented precedence rule.

For an independent-sleeve position, the paper state can persist per sleeve:

- `a_strategy_owner` / `b_strategy_owner`;
- `a_strategy_ownership_source` / `b_strategy_ownership_source`.

Failed or waiting entries do not fabricate ownership. Re-entry ownership is written only after the core paper ledger has actually moved that position out of SGOV.

The next lifecycle-routing milestone must make SELL evaluation read these persisted owner fields before closing positions. This is intentionally separate from the ownership-persistence milestone so persistence can be regression-tested before changing exit authority in the daily paper loop.

## Enterprise evidence fields

Dividend symbol-specific Entry Score evidence can include a `strategy_signals` object containing:

- `available`;
- `source_timeframe`;
- `strategy_a.name`;
- `strategy_a.entry_armed`;
- `strategy_a.arming_reasons`;
- `strategy_a.buy_trigger`;
- `strategy_a.sell_trigger`;
- `strategy_a.buy_reasons`;
- `strategy_a.sell_reasons`;
- `strategy_a.rsi14`;
- Stochastic Oscillator `(14,3,3)` K/D and prior K/D;
- Stochastic RSI `(14,7,3,3)` K/D and prior K/D;
- `strategy_a.stoch_rsi.k_above_d`;
- `strategy_a.stoch_rsi.k_rising`;
- `strategy_b.buy_eligible`;
- `strategy_b.sell_trigger`;
- `strategy_b.buy_reason`;
- `strategy_b.sell_reason`;
- Strategy B Price, EMA20, and EMA50.

Strategy ownership evidence can include:

- `strategy_owner`;
- `eligible_strategies`;
- `ownership_source`;
- `entry_allowed_by_ownership`;
- explicit ownership resolution/wait reason;
- owner-specific SELL authority and reason codes.

Missing or insufficient market evidence remains fail-closed.

## Entry status contract

The Enterprise host can continue consuming:

- `STRONG_ENTRY`
- `GOOD_ENTRY`
- `WATCH`
- `WAIT`
- `AVOID`
- `UNKNOWN`

Opportunity Quality and Entry Timing remain separate. High Opportunity Quality does not authorize an entry by itself.

## AI CIO implications

The AI CIO should eventually be able to explain which Dividend timing strategy is active, which strategy owns an open position, and why. Examples:

- `Strategy A armed by STOCH_OSC_K_ABOVE_D_AND_AT_OR_ABOVE_50`;
- `Strategy A remains armed because RSI14_AT_OR_ABOVE_50`;
- `Strategy A BUY lever active because STOCH_RSI_K_ABOVE_D`;
- `Strategy A SELL caused by STOCH_RSI_D_CROSSED_ABOVE_K`;
- `Strategy B BUY eligible because PRICE_ABOVE_EMA20_ABOVE_EMA50`;
- `Strategy B SELL because PRICE_BELOW_EMA20`;
- `WAIT because NO_ACTIVE_ENTRY_STRATEGY`;
- `WAIT because MULTIPLE_ACTIVE_ENTRY_STRATEGIES_REQUIRE_SELECTION_POLICY`;
- `Existing position remains owned by STRATEGY_A despite a Strategy B signal`.

The Enterprise host must display supplied strategy evidence; it must not recompute Dividend or Swing trading logic.

## Swing compatibility requirement

SWING-001 must **not** copy Dividend's Strategy A or Strategy B formulas unless Swing independently chooses those rules for its own strategy.

Swing should instead publish its own strategy-owned entry/exit methodology through equivalent semantic evidence where useful:

- strategy/method identifier;
- candidate symbol or pair;
- entry status;
- entry score if used;
- whether its entry mechanism is armed/eligible;
- exact BUY trigger evidence;
- exact SELL trigger evidence;
- prior/current values needed to prove a crossover rather than a touch when Swing uses crossover rules;
- strategy owner/method owner for an open lifecycle if Swing supports multiple timing methods;
- persisted owner/method field in Swing's own position lifecycle once a position is actually opened;
- explicit WAIT/rejection reasons;
- requirements/next trigger;
- market-data freshness;
- source/provenance;
- paper-only and broker-disabled safety flags.

If Swing uses multiple entry methodologies, Swing should preserve the method that actually owns an open position and must not silently switch exit logic mid-position. If multiple Swing methods simultaneously qualify a new candidate, Swing should publish its own documented selection/precedence rule or fail closed until one is selected. Dividend's current fail-closed ambiguity policy is not automatically Swing's required policy; the semantic requirement is that ownership and precedence be explicit and auditable.

Swing should persist ownership in its own authoritative paper lifecycle/state rather than relying only on a transient dashboard field. The AI CIO may display that ownership, but it must not become the system of record for Swing lifecycle ownership.

If Swing uses RSI, EMA, Stochastic, Stochastic RSI, HMA, ATR, volume, breakout structure, committee votes, or another model, those values remain Swing-owned evidence. The AI CIO should aggregate/display them without applying Dividend formulas to Swing.

## Cross-strategy permanent rules

- Opportunity Quality answers whether an opportunity is attractive.
- Entry Timing answers whether capital should be deployed now.
- A WAIT must have an explicit reason whenever strategy evidence supports one.
- Missing/UNKNOWN evidence fails closed.
- SELL crossovers require prior/current evidence and cannot be inferred from lines merely touching.
- Open-position strategy ownership remains stable until that lifecycle is closed or explicitly migrated by a documented policy.
- Strategy calculations remain owned by their source strategy.
- The Enterprise AI CIO aggregates, governs, and displays; it does not silently replace strategy logic.

## Swing regression tests to add

Swing development should add tests proving that:

1. missing entry evidence fails closed;
2. stale technical evidence cannot become an approved entry;
3. candidate-specific evidence is not replaced by a global score;
4. high Opportunity Quality cannot bypass failed Entry Timing;
5. every WAIT/rejected entry has a reason code;
6. any crossover-based Swing SELL rule distinguishes a true cross from equality/touching;
7. entry and exit reasons identify the responsible Swing mechanism;
8. if Swing supports multiple timing methods, open-position method ownership is sticky;
9. one Swing method cannot sell a position owned by another method unless a documented migration/override policy explicitly permits it;
10. ambiguous multiple-method entry qualification has an explicit selection policy or fails closed;
11. ownership is persisted in Swing's authoritative paper position lifecycle/state after a position opens;
12. a failed/waiting entry does not fabricate ownership;
13. cross-strategy evidence cannot be consumed as SWING-001 evidence;
14. paper-only, no-order, and broker-disabled flags remain locked;
15. canonical Swing evidence reaches the Enterprise registry at its declared path.

## Dividend files changed for this strategy timing / ownership milestone

- `src/dividend_bot/dividend_entry_strategy_signals.py`
- `src/dividend_bot/dividend_technical_entry_evidence.py`
- `src/dividend_bot/dividend_strategy_ownership.py`
- `paper_trading_engine.py`
- `tests/test_dividend_entry_strategy_signals.py`
- `tests/test_dividend_entry_score_market_evidence.py`
- `tests/test_dividend_strategy_ownership.py`
- `tests/test_paper_trading_strategy_ownership_persistence.py`

This addendum should be consolidated into `SWING_ENTERPRISE_UI_COMPATIBILITY_TRACKER.md` during the next documentation consolidation pass.