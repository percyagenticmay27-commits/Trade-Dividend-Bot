# AI CIO Discovery Leadership

## Philosophy

**AI CIO discovers leadership. SWING-001 evaluates the trade.**

Discovery Leadership answers: **Where does market leadership and capital concentration appear to exist, and which securities deserve deeper SWING-001 analysis?**

Market-relative leadership is discovery evidence. It is **not** an entry signal, a BUY instruction, or trading authorization.

## Architecture boundary

```text
MARKET UNIVERSE
        ↓
MARKET REGIME
        ↓
SECTOR / INDUSTRY LEADERSHIP
        ↓
THEME MOMENTUM
        ↓
STOCK RELATIVE LEADERSHIP VS SPY
        ↓
SOURCE / MARKET INTELLIGENCE CONFLUENCE
        ↓
AI CIO SWING DISCOVERY CANDIDATE
        ↓
enterprise_swing_discovery_bucket.json
        ↓
SWING-001
        ↓
Opportunity Quality
        ↓
Technical / Setup Analysis
        ↓
Entry Score
        ↓
Opportunity Rank
        ↓
Capital Allocation
```

The following remain SWING-001 responsibilities and are deliberately excluded from AI CIO Discovery Leadership: SMA20/SMA50/SMA200 entry rules, pullback confirmation, base detection, pivot/breakout detection, technical volume confirmation, Entry Score, Opportunity Quality, strategy exit logic, and paper-position management.

## Relative leadership evidence

The benchmark is `SPY`. AI CIO consumes existing local daily history from `historical_data/daily/<SYMBOL>.csv`; this module never fetches market data over the network.

Where enough aligned stock and benchmark history exists, the engine evaluates approximately 1-month (21 sessions), 3-month (63), 6-month (126), and year-to-date returns. It records stock return, benchmark return, relative outperformance, a performance multiple when mathematically meaningful, period dates, data timestamps, and freshness.

The Trapper methodology's approximate `2x SPY` concept is treated as strong supporting leadership evidence, not as an inflexible gate. The multiple is suppressed when SPY's return is non-positive or below 1%, because ratios around zero or through negative returns are misleading. Absolute stock return and percentage-point outperformance remain visible.

### Classification thresholds

Per-horizon relative outperformance is classified with centralized thresholds in `src/dividend_bot/discovery_leadership.py`:

- below -5 percentage points: `WEAK`
- -5 through +5: `MARKET_PERFORMER`
- above +5 through +12: `STRONG`
- above +12 through +25: `LEADER`
- above +25: `EXCEPTIONAL_LEADER`

A meaningful `2x SPY` result with at least +5 percentage points of outperformance can elevate supporting evidence to `LEADER`; it never operates as a binary admission gate.

Multi-horizon results are aggregated into a 0-100 leadership score and a `leadership_persistence` value representing the share of evaluated horizons classified `LEADER` or better.

## Sector and industry leadership

The current AI CIO repository does not contain a separate authoritative sector/industry index-strength engine. To avoid fabricating evidence, this enhancement uses the relative-leadership scores of the **current discovery candidate population** as peer evidence when at least two evaluable candidates share a sector or industry. The artifact records the method as `DISCOVERY_CANDIDATE_PEER_AVERAGE`.

Missing sector, industry, or insufficient peer evidence does not reject a candidate. It produces an explicit missing-evidence warning.

If a future authoritative sector/industry benchmark service is added, it can replace this peer assessment without changing the SWING-001 top-level contract.

## Theme momentum and source confluence

Existing explicit theme-momentum evidence is consumed when present. A theme label by itself is not treated as momentum. If explicit theme momentum is unavailable, the artifact reports `THEME_MOMENTUM_EVIDENCE_MISSING`.

Existing AI CIO source-confluence levels (`NONE`, `SINGLE_SOURCE`, `CONFIRMED`, `STRONG`) contribute to the composite assessment. Numeric market leadership remains the primary component.

## Composite Discovery Leadership

Available evidence is combined with these weights, renormalized across available components:

- stock relative leadership: 60%
- sector leadership: 15%
- industry leadership: 15%
- theme momentum: 5%
- source confluence: 5%

A composite score is not published when stock-relative market data is missing. That prevents news/source evidence alone from masquerading as measured market leadership.

Candidates are ranked deterministically by Discovery Leadership score, with missing-score candidates last and ticker as the final tie-breaker. There is no hard 20-stock AI CIO limit.

## SWING-001 compatibility

The established top-level contract remains:

```json
{
  "schema_version": "1.0",
  "strategy_id": "SWING-001",
  "candidates": []
}
```

Existing required candidate fields remain intact. The enhancement adds only backward-compatible fields:

- `relative_leadership`
- `sector_leadership`
- `industry_leadership`
- `theme_leadership`
- `discovery_leadership_score`
- `discovery_leadership_classification`
- `discovery_reasons`
- `discovery_warnings`

Explainability reasons can include `OUTPERFORMING_SPY`, `TRAPPER_2X_SPY_EVIDENCE`, `MULTI_HORIZON_LEADER`, `MARKET_LEADER`, `LEADING_SECTOR`, `LEADING_INDUSTRY`, `RISING_THEME`, and `STRONG_SOURCE_CONFLUENCE`.

## Safety

This enhancement does not modify Dividend strategy logic, portfolio execution, allocation, brokerage integration, or real-trading capability. Existing paper-only and enterprise safety controls remain authoritative and unchanged.

A discovered exceptional leader may still be extended, pulling back, basing, near a pivot, or otherwise unsuitable for entry. Those determinations belong downstream to SWING-001.
