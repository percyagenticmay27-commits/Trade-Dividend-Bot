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
- The initial production source catalog enables only broad SEC daily-index
  evidence. Company-specific IR feeds will be added only after their official
  HTTPS endpoints are verified; example placeholder URLs are never executed.

## 2026-08-18 — Bounded YouTube evidence adapter

- The owner configured `YOUTUBE_API_KEY` only in the protected server
  environment file. The key is never written to configuration, artifacts,
  warnings, logs, tests, or handoff documentation.
- `YOUTUBE_SEARCH` sources use a seven-day window, at most 25 results per
  request, and a 500-unit per-run search budget. Exhaustion degrades with an
  explicit warning rather than issuing unbounded requests.
- Video popularity is not authority. Only a source with a verified channel ID,
  `credibility_reviewed=true`, and authority `REVIEWED_CREATOR` or
  `PROFESSIONAL_MEDIA` may independently confirm an existing company lead.
- Symbols are matched only against the existing underlying-company research
  universe. Unknown prose tokens and leveraged/inverse products cannot become
  nominations. A YouTube result alone remains research-only.
- The production catalog is intentionally unchanged until each seed channel's
  canonical channel ID and credibility profile are manually validated. The
  Saturday timer remains uninstalled and disabled.
- `scripts/review_youtube_discovery_channels.py` performs a one-time bounded
  channel search for the six initial seed examples and writes only an
  `UNVERIFIED` human-review artifact. It never edits the production catalog or
  automatically approves a search result, protecting against similarly named
  and impersonating channels.
- The review tool's `--enrich-existing` mode uses one batched channels lookup
  to attach the official handle, creation date, country, subscriber count, and
  video count. Metadata improves human identity review but never changes the
  `UNVERIFIED` gate or production configuration.
- Human review approved five unique initial sources: Joseph Hogue
  (`@josephhogue`), Earn Your Leisure (`@earnyourleisure`), Business With
  Brian (`@businesswithbrian`), CBS News (`@cbsnews`), and Ticker Symbol: YOU
  (`@tickersymbolyou`). “Bow Tie Nation” is Joseph Hogue's community name and
  is not configured as the unrelated nine-subscriber look-alike channel.
- The five searches consume the full configured 500-unit weekly search budget.
  Short one- and two-letter symbols require explicit cashtags, preventing
  ordinary prose such as “be” from being interpreted as ticker `BE`.

### Direct script execution correction

The first controlled server run exposed that executing a Python file beneath
`scripts/` sets that directory, rather than the repository root, as the first
import location. Both scheduled commands now insert their resolved repository
root before importing host modules. Dedicated tests load each script exactly by
path so compilation-only validation cannot miss this deployment behavior again.

### SEC exchange and security-type noise reduction

The first controlled live collection returned 1,676 evidence-only symbols and
showed that the simpler ticker association file includes OTC securities, units,
preferred shares, and multiple classes. The broad collector now uses SEC's
exchange association file, accepts only Nasdaq, NYSE, and NYSE American rows,
rejects obvious units/warrants/preferred products, and deterministically chooses
one common underlying ticker per CIK. This is discovery-pool hygiene only; all
broad SEC observations remain ineligible until independently confirmed.

### Research pool versus active nominations

The live filtered run produced 1,528 valid exchange-listed company leads. These
are still too broad to be strategy nominations. The rich weekly artifact now
stores `nomination_eligible=false` rows under `research_evidence_pool`, not
`candidates`. Both Swing and Dividend projections consume only active confirmed
`candidates`. Research-only rows remain append-only historical evidence and may
become eligible in a later cycle only when an independent producer supplies
confirming evidence; counts never promote rows.
