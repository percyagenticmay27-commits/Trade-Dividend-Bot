# Swing Entry Score / AI CIO Compatibility Addendum

## Purpose

This addendum records the Enterprise-facing consequences of the Dividend Entry Score Version 1.1 development. It must be used by the Swing Bot development chat as a compatibility handoff. The Dividend repository remains the Enterprise AI CIO host; no changes in this document authorize modifying the Swing repository from the Dividend repository.

## Dividend-side change

DIVIDEND-001 now derives symbol-specific entry-timing evidence from the already-fetched shared market-data snapshot instead of using the legacy global `entry_score = 0` / `entry_status = UNKNOWN` placeholder whenever sufficient daily history exists.

Dividend Entry Score evidence now evaluates strategy-owned timing using:

- RSI14;
- EMA20;
- EMA50;
- bullish `Price > EMA20 > EMA50` alignment;
- HMA50 and whether HMA50 is rising;
- Fast Stochastic %K, slope, and whether it is rising;
- Fast Stochastic overextension protection;
- five-day price direction;
- market-data freshness;
- history sufficiency.

The legacy deterministic `UNKNOWN` fallback remains mandatory when sufficient market evidence is unavailable.

### Fast Stochastic overextension protection

Dividend Entry Score Version 1.1.1 treats Fast Stochastic `%K >= 90` as an explicit overextension blocker even when `%K` is still rising. This prevents a high raw score from converting a late/chasing setup into an approved entry.

Dividend publishes:

- `FAST_STOCHASTIC_OVEREXTENDED` in `reasons`;
- `Fast Stochastic must cool below 90 before entry` in `requirements_for_buy`;
- `timing_context = OVEREXTENDED`;
- `technical_evidence.fast_stochastic_overextended = true`;
- `technical_evidence.fast_stochastic_overextended_threshold = 90.0`.

This threshold is Dividend strategy logic, not an Enterprise-wide or Swing threshold.

## Entry status contract

The host can consume these statuses:

- `STRONG_ENTRY`
- `GOOD_ENTRY`
- `WATCH`
- `WAIT`
- `AVOID`
- `UNKNOWN`

For DIVIDEND-001, only `GOOD_ENTRY` and `STRONG_ENTRY` may satisfy the Dividend Entry Gate. A high Opportunity Quality or ranking score does not override a weak Entry Score or an overextension blocker.

Every non-approved entry should publish explicit reasons and, where deterministically known, requirements that would need to change before a BUY could be considered. Example fields include:

- `entry_score`
- `entry_status`
- `timing_context`
- `confidence`
- `confidence_level`
- `technical_signal`
- `reasons`
- `requirements_for_buy`
- `technical_evidence`
- `market_data_stale`
- `history_row_count`
- `source`

## Fail-closed AI CIO behavior

The Enterprise AI CIO must not interpret missing or `UNKNOWN` Entry Score evidence as approval. The strategy-owned entry gate remains authoritative for strategy execution eligibility.

A Dividend WAIT can now include multiple independent blockers, for example:

- `WATCHLIST_NOT_PROMOTED_WATCH`
- `ENTRY_STATUS_NOT_APPROVED_WAIT`
- `ENTRY_EVIDENCE_RSI14_BELOW_50`
- `ENTRY_EVIDENCE_EMA20_EMA50_BULLISH_ALIGNMENT_NOT_CONFIRMED`
- `ENTRY_EVIDENCE_PRICE_BELOW_HMA50`
- `ENTRY_EVIDENCE_FAST_STOCHASTIC_NOT_RISING`
- `ENTRY_EVIDENCE_FAST_STOCHASTIC_OVEREXTENDED`

The host UI should display the reason rather than a naked `WAIT` label whenever the strategy publishes reason evidence.

## Swing compatibility requirement

SWING-001 must **not** copy the Dividend indicator thresholds, scoring weights, overextension threshold, or pair-entry policy. Swing owns its own Entry Score methodology and committee rules.

To obtain equivalent AI CIO display and auditability, Swing should publish symbol/candidate-specific entry evidence using the same semantic concepts where applicable:

- canonical `strategy_id = SWING-001`;
- candidate `symbol` or Swing candidate identifier;
- numeric `entry_score` bounded to the Swing Entry Score contract;
- `entry_status` using a documented Swing-to-Enterprise semantic mapping;
- explicit reason codes for `WAIT`, `WATCH`, `AVOID`, overextension, or rejected promotion;
- human-readable requirements or next triggers when deterministic;
- `timing_context`, including an overextended/chasing state if Swing has one;
- `market_data_stale` or equivalent freshness state;
- evidence provenance/path;
- technical/committee evidence owned by Swing;
- paper-only and broker-disabled safety flags.

If Swing uses RSI, EMA, HMA, Stochastic, breakout structure, ATR, volume, committee votes, or another timing model, Swing should publish those values as Swing-owned evidence. If Swing has its own overextension/chasing rule, publish the strategy-owned threshold and blocker so AI CIO can explain it. The Enterprise host must display the supplied evidence but must never recompute Swing's Entry Score using Dividend formulas.

## Opportunity Quality versus Entry Timing

This separation is permanent across strategies:

- **Opportunity Quality** answers whether the candidate is attractive.
- **Entry Score / Entry Timing** answers whether this is an acceptable time to deploy capital.

A strategy may report very high Opportunity Quality while simultaneously reporting `WAIT` for entry. The AI CIO dashboard must preserve both values rather than collapsing them into one score.

## Watchlist / promotion interaction

Dividend currently requires both strategy-owned promotion and acceptable Entry Score before a paper purchase can be approved. Swing may use a different lifecycle, but if it has an equivalent committee promotion stage it should publish the state separately from Entry Score so the AI CIO can explain whether a candidate is waiting because of:

- discovery/ranking;
- committee/watchlist promotion;
- entry timing;
- overextension/chasing risk;
- risk/governance;
- stale or insufficient evidence.

## AI CIO display expectations

For any strategy that publishes sufficient evidence, jshouseapi.com should eventually be able to display:

- candidate/pair;
- Opportunity Quality;
- Entry Score and Entry Status;
- timing context, including `OVEREXTENDED` when published;
- promotion/watchlist state;
- final strategy decision;
- confidence;
- primary blocking reason;
- additional reason codes;
- requirements for the decision to change;
- evidence freshness/source.

The host remains presentation/aggregation only. It does not approve a Swing trade on Swing's behalf.

## Swing regression tests to add

Swing development should add tests proving that:

1. missing entry evidence fails closed;
2. stale technical evidence cannot become an approved entry;
3. candidate-specific entry evidence is not replaced by a global score;
4. a high Opportunity Quality score cannot bypass a failed Entry Timing decision;
5. every `WAIT`/rejected entry contains a reason code;
6. if Swing implements overextension/chasing protection, an overextended setup cannot be approved merely because momentum is still rising;
7. cross-strategy evidence cannot be consumed as SWING-001 evidence;
8. paper-only, no-order, and broker-disabled flags remain locked;
9. the canonical Swing artifact reaches the Enterprise registry at the declared path.

## Files changed on the Dividend side for this milestone

- `src/dividend_bot/dividend_technical_entry_evidence.py`
- `entry_score_engine.py`
- `dividend_entry_gate.py`
- `stage_input_adapters.py`
- `tests/test_dividend_entry_score_market_evidence.py`

This addendum should be merged into `SWING_ENTERPRISE_UI_COMPATIBILITY_TRACKER.md` during the next documentation consolidation pass.
