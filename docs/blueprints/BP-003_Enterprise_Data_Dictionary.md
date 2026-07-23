# BP-003 — Enterprise Data Dictionary

**Version:** 1.0.0  
**Status:** FROZEN

## 1. Purpose

This document defines canonical field names, data types, nullability, validation, and semantics for Platform Version 1. PostgreSQL is the target durable store, while Version 1 may continue using JSON, CSV, and Markdown adapters where already implemented.

## 2. Global Standards

- Database and serialized field names use `snake_case`.
- Entity table names are singular.
- Internal identifiers use UUID.
- Human identifiers use uppercase prefixes and yearly sequences.
- Timestamps use timezone-aware ISO-8601 UTC values.
- Monetary values use decimal semantics, never binary floating point for persisted accounting values.
- Percentages are stored consistently as percentage points unless a field explicitly ends with `_ratio`.
- Historical and governance records are append-only.
- Every strategy-scoped record requires `strategy_id` and `strategy_version`.

## 3. Common Fields

| Field | Type | Required | Rules |
|---|---|---:|---|
| `id` | UUID | Yes | Immutable internal primary key |
| `external_id` | VARCHAR(32) | Yes | Human-friendly unique identifier |
| `created_at` | TIMESTAMPTZ | Yes | UTC creation timestamp |
| `updated_at` | TIMESTAMPTZ | Yes | UTC latest update timestamp |
| `version` | VARCHAR(20) | Yes | Semantic version where applicable |
| `status` | VARCHAR(40) | Yes | Controlled enum per entity |
| `metadata` | JSONB | No | Extension data; must not replace required fields |

## 4. Company

| Field | Type | Required | Rules |
|---|---|---:|---|
| `company_id` | UUID | Yes | Primary key |
| `company_external_id` | VARCHAR(32) | Yes | Prefix `CMP` |
| `legal_name` | VARCHAR(255) | Yes | Official company name |
| `display_name` | VARCHAR(255) | Yes | Report-facing name |
| `primary_symbol` | VARCHAR(24) | Yes | Uppercase normalized ticker |
| `exchange` | VARCHAR(40) | Yes | Normalized exchange code/name |
| `sector` | VARCHAR(120) | No | Shared classification |
| `industry` | VARCHAR(160) | No | Shared classification |
| `country_code` | CHAR(2) | No | ISO country code |
| `company_status` | VARCHAR(30) | Yes | `ACTIVE`, `INACTIVE`, `MERGED`, `DELISTED`, `ARCHIVED` |

## 5. Asset

| Field | Type | Required | Rules |
|---|---|---:|---|
| `asset_id` | UUID | Yes | Primary key |
| `asset_external_id` | VARCHAR(32) | Yes | Prefix `AST` |
| `company_id` | UUID | No | Null for non-company funds/benchmarks |
| `symbol` | VARCHAR(24) | Yes | Uppercase normalized symbol |
| `asset_type` | VARCHAR(40) | Yes | Equity, ETF, leveraged ETF, fund, cash reserve, benchmark |
| `underlying_asset_id` | UUID | No | Required for derivative/leveraged relationships where known |
| `leverage_factor` | NUMERIC(8,4) | No | Example `2.0000` |
| `currency_code` | CHAR(3) | Yes | ISO currency |
| `is_active` | BOOLEAN | Yes | Current availability flag |

## 6. Master Company Intelligence Profile

| Field | Type | Required | Rules |
|---|---|---:|---|
| `mcip_id` | UUID | Yes | Primary key |
| `mcip_external_id` | VARCHAR(32) | Yes | Prefix `MCIP` |
| `company_id` | UUID | Yes | Unique logical one-to-one company relationship |
| `profile_version` | VARCHAR(20) | Yes | Semantic version |
| `as_of` | TIMESTAMPTZ | Yes | Intelligence effective time |
| `discovery_score` | NUMERIC(6,2) | No | Defined platform range |
| `fundamental_score` | NUMERIC(6,2) | No | Shared intelligence only |
| `growth_score` | NUMERIC(6,2) | No | Shared intelligence only |
| `income_score` | NUMERIC(6,2) | No | Shared intelligence only |
| `financial_health_score` | NUMERIC(6,2) | No | Shared intelligence only |
| `risk_score` | NUMERIC(6,2) | No | Direction defined by service contract |
| `technical_score` | NUMERIC(6,2) | No | Calculated facts, not strategy action |
| `market_intelligence_score` | NUMERIC(6,2) | No | Shared intelligence only |
| `earnings_risk_level` | VARCHAR(30) | No | Controlled classification |
| `quality_status` | VARCHAR(30) | Yes | `COMPLETE`, `PARTIAL`, `STALE`, `INVALID` |
| `warnings` | JSONB | No | Explicit missing/conflicting evidence warnings |

The MCIP must not contain entry, exit, allocation, hold, trim, or re-entry decisions.

## 7. Evidence

### Evidence Record

| Field | Type | Required | Rules |
|---|---|---:|---|
| `evidence_id` | UUID | Yes | Primary key |
| `evidence_external_id` | VARCHAR(32) | Yes | Prefix `EVR` |
| `company_id` | UUID | No | At least one supported subject relationship required |
| `asset_id` | UUID | No | Optional subject |
| `evidence_type` | VARCHAR(50) | Yes | Controlled source/event class |
| `source_name` | VARCHAR(255) | Yes | Source identity |
| `source_reference` | TEXT | No | URL, document ID, report ID, or citation reference |
| `observed_at` | TIMESTAMPTZ | Yes | Event observation time |
| `effective_at` | TIMESTAMPTZ | No | Time evidence became effective |
| `summary` | TEXT | Yes | Concise normalized summary |
| `quality_score` | NUMERIC(6,2) | No | Defined by evidence service |
| `provenance` | JSONB | Yes | Collection and transformation history |

### Evidence Append Entry

| Field | Type | Required | Rules |
|---|---|---:|---|
| `append_id` | UUID | Yes | Primary key |
| `evidence_id` | UUID | Yes | Parent evidence |
| `append_type` | VARCHAR(50) | Yes | Approved constitutional append type |
| `content` | TEXT | Yes | New information; never replacement mutation |
| `actor_type` | VARCHAR(40) | Yes | Platform, committee, investor, source, operator |
| `actor_id` | VARCHAR(120) | No | Actor reference |
| `appended_at` | TIMESTAMPTZ | Yes | UTC timestamp |

## 8. Strategy Definition and Evaluation

| Field | Type | Required | Rules |
|---|---|---:|---|
| `strategy_id` | UUID | Yes | Stable strategy key |
| `strategy_code` | VARCHAR(40) | Yes | Example `DIVIDEND`, `SWING` |
| `strategy_name` | VARCHAR(120) | Yes | Display name |
| `strategy_version` | VARCHAR(20) | Yes | Semantic version |
| `lifecycle_status` | VARCHAR(30) | Yes | Installed/configured/paper-valid/operational/archived |
| `paper_trade_supported` | BOOLEAN | Yes | Must be true for Version 1 |
| `required_intelligence` | JSONB | Yes | Declared MCIP sections |

Strategy Evaluation fields:

| Field | Type | Required | Rules |
|---|---|---:|---|
| `evaluation_id` | UUID | Yes | Primary key |
| `evaluation_external_id` | VARCHAR(32) | Yes | Prefix `EVAL` |
| `strategy_id` | UUID | Yes | Mandatory isolation key |
| `company_id` | UUID | Yes | Evaluated company |
| `asset_id` | UUID | No | Evaluated instrument |
| `mcip_id` | UUID | Yes | Shared intelligence source |
| `evaluation_score` | NUMERIC(6,2) | Yes | Strategy-specific meaning |
| `recommendation_type` | VARCHAR(40) | Yes | Pre-decision recommendation |
| `rationale` | TEXT | Yes | Strategy-specific explanation |
| `evaluated_at` | TIMESTAMPTZ | Yes | UTC timestamp |

## 9. AI CIO Decision

| Field | Type | Required | Rules |
|---|---|---:|---|
| `decision_id` | UUID | Yes | Primary key |
| `decision_external_id` | VARCHAR(32) | Yes | Prefix `DEC` |
| `strategy_id` | UUID | Yes | Mandatory strategy isolation |
| `company_id` | UUID | No | Subject company |
| `asset_id` | UUID | Yes | Subject instrument |
| `evaluation_id` | UUID | No | Source strategy evaluation |
| `decision_state` | VARCHAR(50) | Yes | BP-001 lifecycle enum |
| `paper_action` | VARCHAR(40) | Yes | Non-executable action |
| `confidence_score` | NUMERIC(6,2) | Yes | Contract-defined range |
| `risk_level` | VARCHAR(30) | Yes | Controlled classification |
| `rationale` | TEXT | Yes | Final AI CIO explanation |
| `constitution_version` | VARCHAR(20) | Yes | Governing constitution |
| `supersedes_decision_id` | UUID | No | Historical chain |
| `implemented_at` | TIMESTAMPTZ | No | Paper implementation only |

## 10. Investor Override

| Field | Type | Required | Rules |
|---|---|---:|---|
| `override_id` | UUID | Yes | Primary key |
| `override_external_id` | VARCHAR(32) | Yes | Prefix `OVR` |
| `original_decision_id` | UUID | Yes | Immutable link |
| `investor_id` | UUID | Yes | Authorized actor |
| `reason` | TEXT | Yes | Non-empty required reason |
| `replacement_instruction` | TEXT | Yes | Human direction |
| `created_at` | TIMESTAMPTZ | Yes | UTC timestamp |

## 11. Portfolio and Position

| Field | Type | Required | Rules |
|---|---|---:|---|
| `portfolio_id` | UUID | Yes | Shared portfolio key |
| `portfolio_external_id` | VARCHAR(32) | Yes | Prefix `POR` |
| `paper_trade_mode` | BOOLEAN | Yes | Must be true |
| `base_currency` | CHAR(3) | Yes | Default USD where configured |

Position fields:

| Field | Type | Required | Rules |
|---|---|---:|---|
| `position_id` | UUID | Yes | Primary key |
| `position_external_id` | VARCHAR(32) | Yes | Prefix `POS` |
| `portfolio_id` | UUID | Yes | Parent portfolio |
| `strategy_id` | UUID | Yes | Required attribution |
| `asset_id` | UUID | Yes | Instrument |
| `quantity` | NUMERIC(24,8) | Yes | Non-negative for long-only configurations |
| `average_cost` | NUMERIC(24,8) | Yes | Decimal accounting value |
| `current_price` | NUMERIC(24,8) | No | Latest known price |
| `market_value` | NUMERIC(24,8) | No | Derived/persisted snapshot |
| `unrealized_return_pct` | NUMERIC(10,4) | No | Percentage points |
| `opened_at` | TIMESTAMPTZ | Yes | UTC timestamp |
| `closed_at` | TIMESTAMPTZ | No | Required when closed |
| `position_status` | VARCHAR(30) | Yes | Planned/open/trimmed/closed/archived |

## 12. Report

| Field | Type | Required | Rules |
|---|---|---:|---|
| `report_id` | UUID | Yes | Primary key |
| `report_external_id` | VARCHAR(32) | Yes | Prefix `RPT` |
| `strategy_id` | UUID | No | Required for strategy reports; null only for platform report |
| `report_type` | VARCHAR(60) | Yes | Daily/weekly/monthly/audit/performance/etc. |
| `period_start` | DATE | No | Reporting period |
| `period_end` | DATE | No | Reporting period |
| `generated_at` | TIMESTAMPTZ | Yes | UTC timestamp |
| `source_manifest` | JSONB | Yes | Input files/entities/versions |
| `summary_metrics` | JSONB | Yes | Scope-specific metrics |
| `warnings` | JSONB | No | Missing optional inputs and risk flags |
| `output_paths` | JSONB | Yes | JSON/CSV/Markdown destinations |

A strategy report may reference only one `strategy_id`.

## 13. Audit and Learning

Audit Run:

| Field | Type | Required | Rules |
|---|---|---:|---|
| `audit_id` | UUID | Yes | Primary key, prefix `AUD` externally |
| `audit_scope` | VARCHAR(40) | Yes | Platform, strategy, release, decision, evidence |
| `strategy_id` | UUID | No | Required for strategy audit |
| `result` | VARCHAR(20) | Yes | `PASS`, `WARNING`, `FAIL` |
| `findings` | JSONB | Yes | Structured findings |
| `started_at` | TIMESTAMPTZ | Yes | UTC |
| `completed_at` | TIMESTAMPTZ | Yes | UTC |

Learning Record:

| Field | Type | Required | Rules |
|---|---|---:|---|
| `learning_id` | UUID | Yes | Primary key, prefix `LRN` externally |
| `strategy_id` | UUID | No | Optional strategy attribution |
| `company_id` | UUID | No | Optional subject |
| `decision_id` | UUID | No | Optional source decision |
| `learning_type` | VARCHAR(50) | Yes | Outcome/evidence/committee/policy/ecosystem/etc. |
| `observation` | TEXT | Yes | What occurred |
| `lesson` | TEXT | Yes | Interpreted lesson |
| `proposed_change` | TEXT | No | Requires approval before adoption |
| `recorded_at` | TIMESTAMPTZ | Yes | UTC |

## 14. Null and Missing Evidence Rules

- Null means unavailable or not applicable; these meanings must not be conflated.
- Required missing evidence must create a validation error or explicit warning according to the module contract.
- Missing evidence never receives a favorable default.
- Existing Version 1 modules that define `missing evidence = 0` must preserve that behavior where frozen.
- Optional-file absence must generate warnings rather than failure where the existing contract declares the input optional.

## 15. Change Control

Field removal, semantic changes, identifier changes, or relationship changes require an ADR, migration plan, updated BP-002 and BP-004, schema/version increment, compatibility review, and tests.

---

**Freeze declaration:** BP-003 Enterprise Data Dictionary Version 1.0.0 is complete and frozen.