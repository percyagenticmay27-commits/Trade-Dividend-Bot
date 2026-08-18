# Enterprise Weekly Market Discovery Handoff

## 2026-08-17 — Deterministic foundation

The Enterprise AI CIO host owns a neutral weekly market-discovery layer. Its
production schedule is Saturday at 8:00 PM in `America/Chicago`, but the timer
must remain uninstalled and disabled until collection adapters, focused tests,
and a manual server run pass.

Architecture:

- `enterprise_weekly_market_discovery.py` normalizes collected observations,
  tracks weekly lifecycle and expiration, deduplicates syndicated stories, and
  writes append-only historical observations.
- `results/enterprise_weekly_market_discovery.json` is the rich neutral report.
- `results/enterprise_swing_discovery_bucket.json` is the strict Swing schema
  1.0 projection. It contains underlying symbols only. `NEW` is projected as
  Swing-compatible `EMERGING` while retained as `weekly_lifecycle_status=NEW`.
- `results/enterprise_dividend_discovery_bucket.json` nominates the same
  underlyings for Dividend-owned dividend/income ecosystem research.
- `state/enterprise_market_discovery_history.jsonl` is append-only history.
- Unconfirmed candidates remain active only through their recorded retention
  deadline. After expiration they are omitted from both strategy projections
  and an explicit `STALE` transition is appended to historical observations.

Strategy boundary:

- AI CIO nominates; it does not buy, sell, promote, map leveraged products, or
  mutate either strategy's lifecycle.
- Swing owns leveraged/growth vehicle mapping and Swing promotion.
- Dividend owns dividend/income vehicle mapping and Dividend promotion.
- Missing source input fails closed. Candidate counts never fabricate rows.
- Allocations remain DIVIDEND-001 $5,000 and SWING-001 $4,500.
- The system remains paper-only, advisory-only, and incapable of broker/order
  execution or capital movement.

Credential decision:

- No external credentials are required for this deterministic foundation.
- Before live collectors are added, provide the owner with exact setup steps
  for each required API. Secrets belong in a server environment file, never in
  Git, generated artifacts, logs, or chat.

Continuation:

1. Reconcile and add source adapters for SEC/company feeds and existing market
   data without credentials.
2. Add credential-aware YouTube and Reddit adapters only after owner setup.
3. Add source credibility, story clustering, bullish/bearish evidence, and
   attention acceleration while preserving provenance.
4. Run a manual Saturday-equivalent validation before installing/enabling the
   supplied systemd timer.

## 2026-08-17 — Credential-free authoritative collection

- `enterprise_discovery_source_collector.py` collects only owner-configured
  SEC submissions and HTTPS company/IR RSS or Atom feeds. A configured source
  explicitly binds evidence to an underlying symbol; ticker extraction from
  prose is prohibited.
- SEC requests use the public submissions endpoint, a descriptive operator
  User-Agent, and a minimum interval between requests. The User-Agent is not a
  secret, but the collector fails closed if it is absent.
- `scripts/collect_enterprise_discovery_sources.py` writes the normalized input
  consumed by the deterministic generator. It does not write either strategy's
  lifecycle or watchlist.
- Existing `market_data_snapshot.json` evidence is attached when present. No
  price, volume, momentum, dividend, or freshness value is inferred when the
  host snapshot lacks a matching symbol.
- Malformed, unavailable, insecure, and unsupported sources become warnings;
  they never create candidate rows.
- `configs/enterprise_discovery_sources.example.json` is documentation only.
  Production source entries require real CIKs and official HTTPS feed URLs and
  must be reviewed before use.

## 2026-08-17 — Broad SEC material-filing discovery

- The collector uses the SEC company-ticker association file and recent EDGAR
  daily master indexes to locate underlying companies with new 8-K, 6-K, or
  S-1 evidence. It does not crawl every company's submission history.
- SEC states that its ticker association file is periodically updated and not
  guaranteed complete. Unmapped CIKs are omitted, never guessed.
- Obvious ETF/ETN, inverse, leveraged, daily bull/bear, 2x, and 3x product names
  are excluded from the broad underlying-company association map.
- A filing is factual, neutral activity evidence. It is not a bullish catalyst
  and is marked `nomination_eligible=false` until another independent producer
  confirms the candidate.
- Evidence-only rows remain in the rich neutral report for research but are
  excluded from the strict Swing projection. AI CIO cannot create or promote a
  Swing lifecycle record from a filing alone.
