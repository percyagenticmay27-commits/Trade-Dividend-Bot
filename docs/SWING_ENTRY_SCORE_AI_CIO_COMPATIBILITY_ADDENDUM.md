# Swing Entry Score / AI CIO Compatibility Addendum

## Purpose

This addendum records the Enterprise-facing consequences of the Dividend Entry Score development. It is a compatibility handoff for the Swing Bot development chat. The Dividend repository remains the Enterprise AI CIO host; nothing here authorizes changing the Swing repository from the Dividend repository.

## Dividend-side Strategy A / Strategy B timing model

DIVIDEND-001 now publishes two distinct strategy-owned timing models from already-fetched daily OHLC evidence.

### Strategy A — Oscillator / Momentum

The arming mechanism uses:

- Stochastic Oscillator `(14,3,3)` where `%K > %D` and `%K >= 50`, **or**
- RSI(14) crossing from below into `>= 50`.

Once armed, the execution lever is Stochastic RSI `(14,7,3,3)`.

A Strategy A BUY trigger requires:

- Stochastic RSI `%K` genuinely crossing above `%D`; and
- `%K` entering/crossing the 50 level or the 80 level.

A Strategy A SELL trigger occurs when either:

- Stochastic RSI `%D` genuinely crosses above `%K`; or
- Stochastic Oscillator `%D` genuinely crosses above `%K`.

Touching/equality by itself is not a crossover. The implementation requires an actual side change between the previous and current observations.

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

## Enterprise evidence fields

Dividend symbol-specific Entry Score evidence can now include a `strategy_signals` object containing:

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
- `strategy_b.buy_eligible`;
- `strategy_b.sell_trigger`;
- `strategy_b.buy_reason`;
- `strategy_b.sell_reason`;
- Strategy B Price, EMA20, and EMA50.

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

The AI CIO should eventually be able to explain which Dividend timing strategy is active and why. Examples:

- `Strategy A armed by STOCH_OSC_K_ABOVE_D_AND_AT_OR_ABOVE_50`;
- `Strategy A BUY lever waiting for STOCH_RSI_K_CROSSED_ABOVE_D`;
- `Strategy A SELL caused by STOCH_RSI_D_CROSSED_ABOVE_K`;
- `Strategy B BUY eligible because PRICE_ABOVE_EMA20_ABOVE_EMA50`;
- `Strategy B SELL because PRICE_BELOW_EMA20`.

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
- prior/current values needed to prove a crossover rather than a touch;
- explicit WAIT/rejection reasons;
- requirements/next trigger;
- market-data freshness;
- source/provenance;
- paper-only and broker-disabled safety flags.

If Swing uses RSI, EMA, Stochastic, Stochastic RSI, HMA, ATR, volume, breakout structure, committee votes, or another model, those values remain Swing-owned evidence. The AI CIO should aggregate/display them without applying Dividend formulas to Swing.

## Cross-strategy permanent rules

- Opportunity Quality answers whether an opportunity is attractive.
- Entry Timing answers whether capital should be deployed now.
- A WAIT must have an explicit reason whenever strategy evidence supports one.
- Missing/UNKNOWN evidence fails closed.
- Crossovers require prior/current evidence and cannot be inferred from lines merely touching.
- Strategy calculations remain owned by their source strategy.
- The Enterprise AI CIO aggregates, governs, and displays; it does not silently replace strategy logic.

## Swing regression tests to add

Swing development should add tests proving that:

1. missing entry evidence fails closed;
2. stale technical evidence cannot become an approved entry;
3. candidate-specific evidence is not replaced by a global score;
4. high Opportunity Quality cannot bypass failed Entry Timing;
5. every WAIT/rejected entry has a reason code;
6. any crossover-based Swing rule distinguishes a true cross from equality/touching;
7. entry and exit reasons identify the responsible Swing mechanism;
8. cross-strategy evidence cannot be consumed as SWING-001 evidence;
9. paper-only, no-order, and broker-disabled flags remain locked;
10. canonical Swing evidence reaches the Enterprise registry at its declared path.

## Dividend files changed for this strategy timing milestone

- `src/dividend_bot/dividend_entry_strategy_signals.py`
- `src/dividend_bot/dividend_technical_entry_evidence.py`
- `tests/test_dividend_entry_strategy_signals.py`
- `tests/test_dividend_entry_score_market_evidence.py`

This addendum should be consolidated into `SWING_ENTERPRISE_UI_COMPATIBILITY_TRACKER.md` during the next documentation consolidation pass.
