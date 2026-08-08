# Swing Watchlist Promotion Compatibility Addendum

This addendum accompanies `docs/SWING_ENTERPRISE_UI_COMPATIBILITY_TRACKER.md` for the 2026-08-07 Dividend watchlist-promotion milestone.

## Dividend-side change

The Dividend strategy now owns an explicit reporting-only watchlist-promotion stage. It publishes `watchlist_report.json`, `.md`, and `.csv` after Dividend Ranking and before Candidate Discovery. The Enterprise dashboard prefers this explicit strategy-owned watchlist evidence over inferring watchlist membership from discovery alone.

Dividend promotion policy currently:

- candidate must be absent from current paper holdings;
- ranking `overall_score` must be at least 50;
- `AVOID` candidates are excluded;
- stale market-data candidates are excluded;
- candidates are ordered by Dividend ranking score;
- maximum active watchlist size is 10;
- score >= 80 publishes status `READY`;
- score >= 65 publishes status `MONITOR`;
- score >= 50 publishes status `WATCH`;
- promotion is reporting-only and does not allocate capital or place orders.

Published row evidence can include `rank`, `symbol`, `name`, `status`, `opportunity_score`, component scores, `momentum_score`, `conviction_score` when authoritative, `daily_change_percent`, `market_data_stale`, `currently_held`, recommendation/trend information, and source/provenance paths.

## Swing compatibility requirement

Swing must not copy the Dividend thresholds or Dividend ranking formula. SWING-001 should continue to use its own committee/ranking/lifecycle rules and publish the resulting authoritative Swing watchlist through its canonical `main/results/watchlist_report.json` (or update its Registry declaration to the real path).

For professional host rendering, Swing should publish structured watchlist rows with whatever authoritative fields it owns, especially:

- `rank`;
- `symbol`;
- `name` when known;
- `status` / committee lifecycle state;
- `opportunity_quality` or `opportunity_score` when available;
- `conviction_score` when available;
- `momentum_score` when available;
- `daily_change_percent` when available;
- `market_data_stale`;
- `currently_held`;
- evidence provenance.

The Enterprise host remains display-only. It must never apply Dividend promotion thresholds to SWING-001, and it must never promote, reject, buy, allocate, or remove a Swing candidate on Swing's behalf.

This addendum should be merged into the main compatibility tracker during the next documentation consolidation pass.
