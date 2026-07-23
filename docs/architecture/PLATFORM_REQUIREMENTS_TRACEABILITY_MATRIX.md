# Platform Requirements Traceability Matrix

**Version:** 1.0.0  
**Status:** ACTIVE IMPLEMENTATION CONTROL  
**Applies to:** Trade-Dividend-Bot repository, Platform Version 1, Dividend Strategy Version 1

## Purpose

This document is the implementation control that ensures every approved governance rule, business rule, workflow, UI/reporting template, module boundary, audit requirement, and deployment requirement discussed during the Dividend Bot architecture and audit work is either:

1. already implemented in the repository;
2. formally represented by a frozen blueprint or ADR;
3. mapped to an existing Dividend Bot module for integration; or
4. explicitly listed as a required implementation item before deployment.

No approved requirement may be omitted silently.

## Status Values

- **IMPLEMENTED** — production code and focused tests exist.
- **DOCUMENTED** — frozen blueprint/ADR exists; production integration remains.
- **EXISTING_MODULE** — mature repository capability exists and must be integrated rather than rewritten.
- **IN_PROGRESS** — implementation has started but is not yet complete.
- **REQUIRED_BEFORE_DEPLOYMENT** — release-blocking work remains.
- **FUTURE** — intentionally excluded from Platform Version 1.

## 1. Governance and Constitutional Rules

| Requirement | Status | Repository Evidence | Release Rule |
|---|---|---|---|
| AI CIO is the sole automated final investment decision authority | IMPLEMENTED | `BP-001_AI_CIO_Constitution.md`, `platform_governance.py`, `platform_entities.py` | Must remain true |
| Committees analyze, score, question, and recommend but do not vote or decide | DOCUMENTED | `BP-001_AI_CIO_Constitution.md`, `BP-002_Business_Entity_Catalog.md` | Committee integration required before deployment |
| Investor may approve, request review, or override | IMPLEMENTED | `platform_governance.py` | Override reason and linked history required |
| Original AI CIO decision is preserved after override | IMPLEMENTED | `platform_governance.py` | Immutable history required |
| Decisions use controlled lifecycle states | IMPLEMENTED | `platform_entities.py`, `platform_governance.py` | Invalid transitions must fail |
| Constitution and policies are versioned | DOCUMENTED | BP-001, BP-002, BP-008 | Version registry integration required |
| Frozen rules cannot change silently | IMPLEMENTED | blueprints, ADRs, version registry | ADR/version update required |

## 2. Permanent Safety Rules

| Requirement | Status | Repository Evidence | Release Rule |
|---|---|---|---|
| `paper_trade_mode=True` | IMPLEMENTED | `platform_foundation.py`, `strategy_framework.py` | Release blocking |
| `live_trading_enabled=False` | IMPLEMENTED | same | Release blocking |
| `broker_execution_enabled=False` | IMPLEMENTED | same | Release blocking |
| No real orders or broker execution | IMPLEMENTED/DOCUMENTED | README, BP-008, validation code | Release blocking |
| Secrets must not be committed | DOCUMENTED | `.gitignore`, BP-008 | Deployment audit required |
| Existing paper workflow must remain operational during migration | IN_PROGRESS | BP-008 migration controls | Regression validation required |

## 3. Shared Intelligence Architecture

| Requirement | Status | Repository Evidence | Release Rule |
|---|---|---|---|
| One canonical Company per issuer | IMPLEMENTED | `platform_entities.py` | Company service persistence required |
| One logical MCIP per company | IMPLEMENTED | `platform_entities.py`, ADR-004 | Repository/service enforcement required |
| MCIP contains shared intelligence only | IMPLEMENTED | forbidden strategy-key validation | Release blocking |
| Discovery is shared | EXISTING_MODULE | existing discovery modules | MCIP adapter required |
| Fundamentals are shared | EXISTING_MODULE | existing financial/fundamental modules | MCIP adapter required |
| Growth is shared | EXISTING_MODULE | existing growth/research modules | MCIP adapter required |
| Income intelligence is shared factual data | EXISTING_MODULE | existing dividend/income modules | Separate facts from strategy policy |
| Financial health and risk are shared | EXISTING_MODULE | existing health/risk modules | MCIP adapter required |
| Technical calculations are shared and strategy-neutral | EXISTING_MODULE | existing technical/signal modules | MCIP adapter required |
| Market intelligence is shared | EXISTING_MODULE | `market_intelligence_engine.py` family | MCIP adapter required |
| Earnings intelligence is shared | EXISTING_MODULE | earnings modules | MCIP adapter required |
| Themes and watchlists are shared | EXISTING_MODULE | theme/watchlist modules | Strategy evaluation remains separate |
| Intelligence snapshots preserve history | DOCUMENTED | BP-002/BP-004 | Persistence implementation required |

## 4. Evidence Rules

| Requirement | Status | Repository Evidence | Release Rule |
|---|---|---|---|
| Evidence is append-only | IMPLEMENTED | `platform_governance.py` | Release blocking |
| Evidence is never overwritten or deleted | IMPLEMENTED | repository validation | Release blocking |
| Corrections and follow-ups append to original evidence | IMPLEMENTED | evidence append entry types | Release blocking |
| Source, timestamp, quality, and provenance are preserved | IMPLEMENTED/PARTIAL | `EvidenceRecord` | Provenance adapter validation required |
| Existing evidence registry is integrated, not discarded | IN_PROGRESS | existing registry + new repository | Migration adapter required |

## 5. Strategy Isolation Rules

| Requirement | Status | Repository Evidence | Release Rule |
|---|---|---|---|
| Platform owns shared intelligence and infrastructure | IMPLEMENTED/DOCUMENTED | ADR-004, ADR-006, classification matrix | Must remain true |
| Strategy owns interpretation, entry, exit, holding, and allocation behavior | DOCUMENTED | BP-002, BP-005, ADR-006 | Dividend integration required |
| Dividend, Swing, Options, and future strategies remain independent programs | IMPLEMENTED | `strategy_framework.py` | Release blocking |
| Strategy configurations are separate | IMPLEMENTED | `StrategyConfiguration` | Release blocking |
| Strategy lifecycle is controlled and versioned | IMPLEMENTED | `strategy_framework.py` | Release blocking |
| Swing and Options are not operational in Platform Version 1 | DOCUMENTED | BP-008 | Must remain disabled |

## 6. Reporting and UI Template Rules

| Requirement | Status | Repository Evidence | Release Rule |
|---|---|---|---|
| Shared rendering framework and common visual template | IMPLEMENTED/PARTIAL | `reporting_framework.py` | Existing UI templates must be mapped |
| Dividend daily report remains Dividend-only | IN_PROGRESS | strategy-scoped report model | Legacy integration required |
| Dividend weekly report remains Dividend-only | IMPLEMENTED/PARTIAL | Dividend adapter report model | Production data integration required |
| Dividend monthly report remains Dividend-only | IMPLEMENTED/PARTIAL | Dividend adapter report model | Production data integration required |
| Dividend audits remain separate | IMPLEMENTED/PARTIAL | `audit_framework.py`, Dividend adapter | Existing audit content integration required |
| Swing weekly/monthly/audit outputs must be separate when added | IMPLEMENTED BY CONTRACT | report isolation validation | Future implementation |
| Same template, different metrics and decisions per strategy | IMPLEMENTED BY CONTRACT | reporting framework | UI/template catalog required |
| Executive dashboard and Investor dashboard remain separate views | DOCUMENTED/EXISTING_MODULE | existing AI CIO dashboards and architecture decisions | UI integration audit required |
| Reports support JSON, CSV, and Markdown where applicable | PARTIAL | JSON/Markdown implemented | CSV adapters required before deployment where legacy outputs require CSV |
| Output history must not be overwritten across strategies | IMPLEMENTED | strategy-scoped result paths | Release blocking |

## 7. Workflow Design

Approved workflow:

```text
External Data
  -> Discovery
  -> Company / Asset Resolution
  -> MCIP Refresh
  -> Evidence Append
  -> Shared Intelligence Services
  -> Strategy Evaluation
  -> Strategy Recommendation
  -> Committee Collaboration
  -> Constitutional Review
  -> AI CIO Decision
  -> Paper Portfolio Action
  -> Strategy-Specific Reports
  -> Strategy-Specific Audits
  -> Outcome Observation
  -> Learning
```

| Workflow Area | Status | Release Rule |
|---|---|---|
| Platform runtime/orchestrator | REQUIRED_BEFORE_DEPLOYMENT | Must execute one complete paper cycle |
| Company/MCIP service | REQUIRED_BEFORE_DEPLOYMENT | Must prevent duplicate profiles |
| Existing intelligence engine adapters | REQUIRED_BEFORE_DEPLOYMENT | Must update MCIP without strategy decisions |
| AI CIO integration | REQUIRED_BEFORE_DEPLOYMENT | Must consume MCIP/evidence and preserve decision history |
| Dividend strategy integration | IN_PROGRESS | Must consume existing Dividend logic |
| Portfolio integration | REQUIRED_BEFORE_DEPLOYMENT | Strategy attribution required |
| Report and audit generation | IN_PROGRESS | Daily/weekly/monthly/audit required |
| Learning integration | REQUIRED_BEFORE_DEPLOYMENT | Outcome and ecosystem comparison required |
| Email/cloud scheduling | EXISTING_MODULE | Must pass cloud smoke test |

## 8. Existing Module Preservation and Integration

The following existing capabilities are not to be discarded or duplicated. They must be classified, wrapped, and regression-tested:

- AI CIO decision, stability, evidence, learning, executive dashboard, and system integration modules;
- candidate discovery and ranking modules;
- market intelligence, market regime, research intelligence, conviction, institutional context, technical, signal, and earnings modules;
- portfolio construction, allocation, lifecycle, health, risk, history, performance, attribution, and re-entry modules;
- Dividend income, safety, ranking, payout, lifecycle, exit, and re-entry logic;
- reporting, dashboard, audit, diagnostics, health, runtime metrics, release validation, and email delivery modules;
- cloud launchers, schedules, environment checks, and rollback assets.

Each integrated module must receive one of these migration outcomes:

- **REUSE AS-IS**
- **WRAP AS PLATFORM SERVICE**
- **WRAP AS DIVIDEND STRATEGY SERVICE**
- **DEPRECATE AFTER REPLACEMENT PASSES REGRESSION**
- **ACCEPTED TECHNICAL DEBT**

## 9. Deployment Gate

Deployment is blocked until all rows marked **REQUIRED_BEFORE_DEPLOYMENT** are complete and the automated requirements validator passes.

Minimum deployment evidence:

- all BP and ADR files present;
- platform modules compile;
- focused and regression tests pass or failures are formally classified;
- complete paper-only cycle passes;
- Dividend daily, weekly, monthly, performance, learning, and audit outputs are isolated;
- AI CIO decision and investor override history are preserved;
- cloud health check, email delivery, scheduling, and rollback checks pass;
- no live execution path is available.

## 10. Change Control

This matrix must be updated whenever a requirement is implemented, mapped, deferred, or changed. No module may be considered release-complete unless its relevant requirements have traceable code, tests, documentation, and deployment evidence.
