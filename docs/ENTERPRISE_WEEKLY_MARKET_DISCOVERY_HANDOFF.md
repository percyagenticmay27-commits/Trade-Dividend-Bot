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
- The first controlled live collection exposed ordinary-word collisions for
  `HELP`, `MFG`, and `MINE`. YouTube symbols now require explicit market syntax:
  a cashtag, a parenthesized ticker, or adjacency to stock/share/earnings/ticker
  wording. `SMCI` remained valid through “Super Micro Computer (SMCI) Stock.”
- SEC basic dates such as `20260811` are normalized to `2026-08-11` before the
  strict Swing projection is written.

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

## 2026-08-18 — Confirmed-nominee market evidence

- `enterprise_discovery_market_evidence.py` reuses the host's read-only
  `MarketDataService` and its live-provider/fresh-cache/stale-cache behavior.
- Only `nomination_eligible=true` underlyings are refreshed. The 1,527 broad
  SEC research-only leads do not trigger provider calls.
- Recorded daily history produces completed five-session return, SPY-relative
  strength, prior-volume comparison, volume expansion, and latest dollar
  volume. Sector, industry, and quote type are copied from the authoritative
  quote when reported.
- Missing or insufficient history yields `null` and an explicit PARTIAL or
  UNAVAILABLE disclosure. It never becomes zero and never removes or promotes
  a candidate. Policy is `AUTHORITATIVE_HISTORY_ONLY`; inference is false.
- This adapter reads market data only. It cannot place orders, contact a broker,
  mutate strategy lifecycle state, or change either allocation.

### Non-finite live-session normalization

The first controlled live market-evidence run exposed a Yahoo session containing
volume and a date but a non-finite closing value. Python had treated the value as
present, causing JSON consumers such as jq to display null while completeness
was reported as AVAILABLE. Numeric normalization now rejects NaN and infinity.
The adapter uses the latest complete recorded session, recalculates return and
dollar-volume evidence from finite observations only, and never converts an
unavailable price into zero.


## 2026-08-18 — Independent confluence and evidence disagreement

- The rich neutral report now derives source confluence from unique
  story/producer pairs instead of accepting an unverified precomputed value.
  Syndicated repetitions of one originating story are not independent votes.
- Confluence records independent story count, producer count, evidence classes,
  and a deterministic NONE/SINGLE_SOURCE/CONFIRMED/STRONG level. STRONG requires
  at least three independent stories across at least two evidence classes.
- Bullish, bearish, neutral, mixed, and unspecified evidence counts remain
  separate. The disagreement flag is true only when recorded bullish and
  bearish evidence both exist.
- Evidence stance is never converted into an invented bullish or bearish thesis.
  Explicit theses, catalysts, and risks remain source-owned fields. Confluence
  is informational and cannot promote a Swing or Dividend lifecycle record.


## 2026-08-18 — Weekly attention acceleration

- Attention acceleration compares this cycle's independent story/producer count
  with the prior retained weekly candidate observation. It does not use raw
  mentions, views, likes, subscriber counts, or repeated syndicated coverage.
- The first detected cycle is recorded as NEW_BASELINE with no previous count,
  change, or ratio. It is not mislabeled as accelerating.
- Later cycles deterministically report ACCELERATING, DECELERATING, STABLE, or
  ACCELERATING_FROM_ZERO with current/previous counts, absolute change, and a
  ratio when mathematically supported.
- Attention is evidence context only. It cannot create a bullish thesis,
  promote either strategy's lifecycle, map a vehicle, or authorize a trade.


### Same-cycle generation idempotency

A manual second generation during the same ISO weekly cycle exposed that the
current artifact could be mistaken for a prior-week baseline. Same-week reruns
now retain the original previous-week comparison, previous lifecycle state, and
consecutive-week count. A first-week candidate therefore remains NEW_BASELINE
across repeated validation runs. Only a genuinely later weekly cycle can create
a STABLE, ACCELERATING, or DECELERATING comparison. If an intermediate
same-week artifact was already polluted, first-discovered-this-week evidence
repairs the baseline, week count, and prior state automatically.


## 2026-08-18 — Reviewed professional-news feed boundary

- PROFESSIONAL_RSS supports official HTTPS RSS/Atom feeds only. The source
  must be manually marked credibility-reviewed with PROFESSIONAL_MEDIA
  authority; otherwise it is skipped with a warning.
- Headlines are matched only against the SEC-established exchange-listed
  underlying universe and require explicit ticker/market syntax. A news feed
  cannot introduce an unknown ticker or a leveraged product.
- Publisher, story URL, date, title, and source class remain attached. News
  evidence is neutral unless an upstream authoritative source explicitly
  publishes a stance; the host does not infer sentiment from headline wording.
- A reviewed professional item may independently confirm an existing SEC lead,
  but cannot trade, map a vehicle, or directly promote either strategy.
- No production professional feed is enabled yet. Nasdaq documents official RSS
  publication support, but the former catalog page now redirects to its
  newsroom and the exact endpoint still requires live server validation.
  Reuters/Bloomberg/paywalled pages are not scraped and no access controls are
  bypassed.


### Professional endpoint review workflow

The scripts/review_professional_discovery_feeds.py tool validates one
operator-supplied official HTTPS RSS/Atom endpoint, records XML validity, entry
counts, recent entry counts, and up to five sample headlines in a review
artifact. It never edits production source configuration and never approves a
feed. The first candidate endpoint to test manually is Nasdaq's official-domain
legacy Stocks feed URL. It remains untrusted until the server confirms valid
current XML and the owner reviews the output.


The first DigitalOcean review of the legacy Nasdaq Stocks endpoint timed out.
It remains unapproved and absent from production configuration. Network
timeouts are now recorded as REQUEST_FAILED review artifacts, and malformed
responses as INVALID_XML, without a traceback or any automatic fallback to page
scraping.
