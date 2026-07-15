from __future__ import annotations

import html
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MODULE_NAME = "research_intelligence_engine"
MODULE_VERSION = "1.0.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

SOURCE_STATUS_WEIGHTS = {
    "TRUSTED": 1.00,
    "APPROVED": 0.75,
    "OBSERVATION": 0.35,
    "REDUCED_INFLUENCE": 0.20,
    "RETIRED": 0.00,
}

DEFAULT_SOURCE_REGISTRY = (
    {
        "source_name": "Bow Tie Nation",
        "source_type": "YouTube / Research",
        "status": "TRUSTED",
        "review_cadence": "WEEKLY",
        "expertise": ["technology", "AI infrastructure", "nuclear energy", "robotics"],
        "credibility_score": 85.0,
    },
    {
        "source_name": "Earn Your Leisure",
        "source_type": "Podcast / Research",
        "status": "TRUSTED",
        "review_cadence": "WEEKLY",
        "expertise": ["wealth building", "ETFs", "macroeconomics", "business"],
        "credibility_score": 85.0,
    },
)


@dataclass(frozen=True)
class ResearchMention:
    source_name: str
    published_at: str
    mention_type: str
    subject: str
    sentiment: float = 0.0
    confidence: float = 50.0
    title: str = ""
    summary: str = ""
    event_type: str = ""
    related_symbols: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()


def _clamp(value: Any, lower: float = 0.0, upper: float = 100.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return lower
    if not math.isfinite(number):
        return lower
    return round(max(lower, min(upper, number)), 2)


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    else:
        raise ValueError("published_at is required and must be ISO-8601 compatible")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _normalize_source(source: Mapping[str, Any]) -> dict[str, Any]:
    name = str(source.get("source_name", "")).strip()
    if not name:
        raise ValueError("source_name is required")
    status = str(source.get("status", "OBSERVATION")).strip().upper()
    if status not in SOURCE_STATUS_WEIGHTS:
        raise ValueError(f"invalid source status: {status}")
    return {
        "source_name": name,
        "source_type": str(source.get("source_type", "Research")).strip() or "Research",
        "status": status,
        "review_cadence": str(source.get("review_cadence", "WEEKLY")).strip().upper() or "WEEKLY",
        "expertise": [str(item).strip() for item in source.get("expertise", []) if str(item).strip()],
        "credibility_score": _clamp(source.get("credibility_score", 50.0)),
        "historical_accuracy": _clamp(source.get("historical_accuracy", 50.0)),
        "average_lead_days": _clamp(source.get("average_lead_days", 0.0), 0.0, 3650.0),
        "last_reviewed_at": source.get("last_reviewed_at"),
    }


def _normalize_mention(item: Mapping[str, Any] | ResearchMention) -> dict[str, Any]:
    raw = asdict(item) if isinstance(item, ResearchMention) else dict(item)
    mention_type = str(raw.get("mention_type", "STOCK")).strip().upper()
    if mention_type not in {"STOCK", "THEME", "SECTOR", "EVENT"}:
        raise ValueError(f"invalid mention_type: {mention_type}")
    subject = str(raw.get("subject", "")).strip().upper() if mention_type == "STOCK" else str(raw.get("subject", "")).strip()
    if not subject:
        raise ValueError("mention subject is required")
    source_name = str(raw.get("source_name", "")).strip()
    if not source_name:
        raise ValueError("mention source_name is required")
    published_at = _parse_dt(raw.get("published_at")).isoformat()
    return {
        "source_name": source_name,
        "published_at": published_at,
        "mention_type": mention_type,
        "subject": subject,
        "sentiment": _clamp(float(raw.get("sentiment", 0.0)) + 100.0, 0.0, 200.0) - 100.0,
        "confidence": _clamp(raw.get("confidence", 50.0)),
        "title": str(raw.get("title", "")).strip(),
        "summary": str(raw.get("summary", "")).strip(),
        "event_type": str(raw.get("event_type", "")).strip().upper(),
        "related_symbols": sorted({str(symbol).strip().upper() for symbol in raw.get("related_symbols", []) if str(symbol).strip()}),
        "evidence_ids": sorted({str(eid).strip() for eid in raw.get("evidence_ids", []) if str(eid).strip()}),
    }


def _age_weight(published_at: str, as_of: datetime) -> float:
    age_days = max(0.0, (as_of - _parse_dt(published_at)).total_seconds() / 86400.0)
    if age_days <= 7:
        return 1.00
    if age_days <= 30:
        return 0.75
    if age_days <= 90:
        return 0.40
    if age_days <= 180:
        return 0.15
    return 0.05


def _source_weight(source: Mapping[str, Any]) -> float:
    status_weight = SOURCE_STATUS_WEIGHTS[str(source["status"]).upper()]
    credibility = _clamp(source.get("credibility_score", 50.0)) / 100.0
    accuracy = _clamp(source.get("historical_accuracy", 50.0)) / 100.0
    return status_weight * ((credibility * 0.65) + (accuracy * 0.35))


def _trend_label(recent: float, prior: float) -> str:
    delta = recent - prior
    if delta >= 15:
        return "RISING_FAST"
    if delta >= 5:
        return "RISING"
    if delta <= -15:
        return "FALLING_FAST"
    if delta <= -5:
        return "FALLING"
    return "STABLE"


def _action_for_score(score: float, unique_sources: int, evidence_match: float) -> str:
    if score >= 75 and unique_sources >= 2 and evidence_match >= 55:
        return "BEGIN_DEEP_ANALYSIS"
    if score >= 50 and unique_sources >= 2:
        return "MONITOR_CLOSELY"
    if score >= 25:
        return "MONITOR"
    return "NO_ACTION"


def build_research_intelligence(
    mentions: Sequence[Mapping[str, Any] | ResearchMention] | None = None,
    source_registry: Sequence[Mapping[str, Any]] | None = None,
    internal_evidence_match: Mapping[str, float] | None = None,
    as_of: str | datetime | None = None,
) -> dict[str, Any]:
    """Build a paper-only research-attention report.

    Research attention is a discovery accelerator only. It cannot directly alter
    portfolio allocations, Watchlist status, Opportunity Quality, or production policy.
    """
    as_of_dt = _parse_dt(as_of) if as_of is not None else datetime.now(timezone.utc)
    sources = [_normalize_source(item) for item in (source_registry or DEFAULT_SOURCE_REGISTRY)]
    source_map = {item["source_name"].casefold(): item for item in sources}
    normalized_mentions = [_normalize_mention(item) for item in (mentions or [])]
    evidence_map = {str(key).upper(): _clamp(value) for key, value in (internal_evidence_match or {}).items()}

    warnings: list[str] = []
    for mention in normalized_mentions:
        if mention["source_name"].casefold() not in source_map:
            warnings.append(f"Unregistered research source: {mention['source_name']}")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for mention in normalized_mentions:
        grouped[(mention["mention_type"], mention["subject"])].append(mention)

    intelligence_items: list[dict[str, Any]] = []
    for (mention_type, subject), items in grouped.items():
        weighted_points = 0.0
        max_possible = 0.0
        sentiments: list[float] = []
        unique_sources: set[str] = set()
        recent_points = 0.0
        prior_points = 0.0
        evidence_ids: set[str] = set()
        event_types: set[str] = set()

        for item in items:
            source = source_map.get(item["source_name"].casefold(), {
                "status": "OBSERVATION",
                "credibility_score": 35.0,
                "historical_accuracy": 35.0,
            })
            sw = _source_weight(source)
            aw = _age_weight(item["published_at"], as_of_dt)
            confidence = item["confidence"] / 100.0
            contribution = sw * aw * confidence
            weighted_points += contribution
            max_possible += max(sw, 0.01)
            sentiments.append(item["sentiment"])
            unique_sources.add(item["source_name"])
            evidence_ids.update(item["evidence_ids"])
            if item["event_type"]:
                event_types.add(item["event_type"])
            age_days = (as_of_dt - _parse_dt(item["published_at"])).total_seconds() / 86400.0
            if age_days <= 30:
                recent_points += contribution
            elif age_days <= 90:
                prior_points += contribution

        raw_consensus = 100.0 * weighted_points / max(max_possible, 0.01)
        source_breadth_bonus = min(20.0, max(0, len(unique_sources) - 1) * 7.5)
        consensus_score = _clamp(raw_consensus + source_breadth_bonus)
        attention_score = _clamp((consensus_score * 0.75) + min(25.0, len(items) * 4.0))
        evidence_match = evidence_map.get(subject.upper(), 50.0)
        conviction_score = _clamp(
            (consensus_score * 0.35)
            + (attention_score * 0.20)
            + (evidence_match * 0.35)
            + (min(100.0, len(unique_sources) * 22.0) * 0.10)
        )
        sentiment_average = round(sum(sentiments) / len(sentiments), 2) if sentiments else 0.0
        action = _action_for_score(conviction_score, len(unique_sources), evidence_match)

        intelligence_items.append({
            "mention_type": mention_type,
            "subject": subject,
            "mention_count": len(items),
            "unique_source_count": len(unique_sources),
            "sources": sorted(unique_sources),
            "consensus_score": consensus_score,
            "attention_score": attention_score,
            "research_conviction_score": conviction_score,
            "internal_evidence_match": evidence_match,
            "sentiment_average": sentiment_average,
            "attention_trend": _trend_label(recent_points * 100.0, prior_points * 100.0),
            "recommended_action": action,
            "event_types": sorted(event_types),
            "evidence_ids": sorted(evidence_ids),
            "governance_note": "Research attention triggers analysis only; it does not create ranking or allocation entitlement.",
        })

    intelligence_items.sort(
        key=lambda row: (row["research_conviction_score"], row["attention_score"], row["unique_source_count"]),
        reverse=True,
    )

    stocks = [row for row in intelligence_items if row["mention_type"] == "STOCK"]
    themes = [row for row in intelligence_items if row["mention_type"] in {"THEME", "SECTOR"}]
    events = [row for row in intelligence_items if row["mention_type"] == "EVENT"]
    deep_analysis = [row for row in intelligence_items if row["recommended_action"] == "BEGIN_DEEP_ANALYSIS"]

    report = {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "generated_at": as_of_dt.isoformat(),
        "paper_trade_mode": PAPER_TRADE_MODE,
        "live_trading_enabled": LIVE_TRADING_ENABLED,
        "broker_execution_enabled": BROKER_EXECUTION_ENABLED,
        "reporting_only": REPORTING_ONLY,
        "research_directly_changes_rankings": False,
        "research_directly_allocates_capital": False,
        "weekly_review_required": True,
        "source_registry": sources,
        "summary": {
            "sources_registered": len(sources),
            "sources_reviewed": len({m["source_name"] for m in normalized_mentions}),
            "mentions_reviewed": len(normalized_mentions),
            "stock_subjects": len(stocks),
            "theme_or_sector_subjects": len(themes),
            "event_subjects": len(events),
            "deep_analysis_triggers": len(deep_analysis),
            "average_research_conviction": round(
                sum(row["research_conviction_score"] for row in intelligence_items) / len(intelligence_items), 2
            ) if intelligence_items else 0.0,
        },
        "stock_intelligence": stocks,
        "theme_intelligence": themes,
        "event_intelligence": events,
        "attention_heatmap": [
            {
                "rank": index,
                "subject": row["subject"],
                "type": row["mention_type"],
                "mentions": row["mention_count"],
                "sources": row["unique_source_count"],
                "attention_score": row["attention_score"],
                "trend": row["attention_trend"],
                "action": row["recommended_action"],
            }
            for index, row in enumerate(intelligence_items, start=1)
        ],
        "deep_analysis_queue": deep_analysis,
        "warnings": sorted(set(warnings)),
        "governance": {
            "research_generates_hypotheses_only": True,
            "fundamentals_required": True,
            "financial_analysis_required": True,
            "news_validation_required": True,
            "technical_analysis_required": True,
            "opportunity_quality_required": True,
            "watchlist_qualification_required": True,
            "investor_approval_required_for_policy_changes": True,
        },
    }
    return report


def format_research_intelligence_markdown(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AI CIO Research Intelligence",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Executive Summary",
        "",
        f"- Sources registered: {summary['sources_registered']}",
        f"- Sources reviewed: {summary['sources_reviewed']}",
        f"- Mentions reviewed: {summary['mentions_reviewed']}",
        f"- Specific stocks identified: {summary['stock_subjects']}",
        f"- Themes or sectors identified: {summary['theme_or_sector_subjects']}",
        f"- Deep-analysis triggers: {summary['deep_analysis_triggers']}",
        f"- Average Research Conviction Score: {summary['average_research_conviction']:.2f} / 100",
        "",
        "## Stock Attention Heatmap",
        "",
        "| Rank | Stock / Subject | Mentions | Independent Sources | Attention | Trend | Action |",
        "|---:|---|---:|---:|---:|---|---|",
    ]
    for row in report["attention_heatmap"]:
        lines.append(
            f"| {row['rank']} | {row['subject']} | {row['mentions']} | {row['sources']} | "
            f"{row['attention_score']:.2f} | {row['trend']} | {row['action']} |"
        )
    if not report["attention_heatmap"]:
        lines.append("| - | No research mentions supplied | 0 | 0 | 0.00 | STABLE | NO_ACTION |")

    lines.extend([
        "",
        "## Research Sources",
        "",
        "| Source | Type | Status | Cadence | Credibility |",
        "|---|---|---|---|---:|",
    ])
    for source in report["source_registry"]:
        lines.append(
            f"| {source['source_name']} | {source['source_type']} | {source['status']} | "
            f"{source['review_cadence']} | {source['credibility_score']:.2f} |"
        )

    lines.extend([
        "",
        "## Governance",
        "",
        "> Research generates ideas. Evidence earns Watchlist status and capital.",
        "",
        "Research attention cannot directly change rankings, create allocation entitlement, or bypass fundamentals, financial analysis, news validation, technical analysis, Opportunity Quality, or Watchlist qualification.",
    ])
    if report["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    return "\n".join(lines) + "\n"


def format_research_intelligence_html(report: Mapping[str, Any]) -> str:
    markdown = format_research_intelligence_markdown(report)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>AI CIO Research Intelligence</title>"
        "<style>body{font-family:Arial,sans-serif;max-width:1200px;margin:32px auto;padding:0 20px;}"
        "pre{white-space:pre-wrap;line-height:1.45;background:#f7f7f7;padding:24px;border-radius:10px;}</style>"
        "</head><body><pre>" + html.escape(markdown) + "</pre></body></html>"
    )


def write_research_intelligence(report: Mapping[str, Any], root_path: str | Path = ".") -> dict[str, str]:
    root = Path(root_path)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / "research_intelligence.json"
    md_path = root / "research_intelligence.md"
    html_path = root / "research_intelligence.html"
    json_path.write_text(json.dumps(dict(report), indent=2, sort_keys=True), encoding="utf-8")
    md_path.write_text(format_research_intelligence_markdown(report), encoding="utf-8")
    html_path.write_text(format_research_intelligence_html(report), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path), "html": str(html_path)}


def build_and_write_research_intelligence(
    mentions: Sequence[Mapping[str, Any] | ResearchMention] | None = None,
    source_registry: Sequence[Mapping[str, Any]] | None = None,
    internal_evidence_match: Mapping[str, float] | None = None,
    as_of: str | datetime | None = None,
    root_path: str | Path = ".",
) -> dict[str, Any]:
    report = build_research_intelligence(
        mentions=mentions,
        source_registry=source_registry,
        internal_evidence_match=internal_evidence_match,
        as_of=as_of,
    )
    report["output_files"] = write_research_intelligence(report, root_path=root_path)
    return report


def _sample_mentions() -> list[dict[str, Any]]:
    return [
        {
            "source_name": "Bow Tie Nation",
            "published_at": "2026-07-12T15:00:00+00:00",
            "mention_type": "STOCK",
            "subject": "OKLO",
            "sentiment": 72,
            "confidence": 88,
            "title": "Nuclear power and AI infrastructure",
            "event_type": "GROWTH_OUTLOOK",
        },
        {
            "source_name": "Earn Your Leisure",
            "published_at": "2026-07-13T15:00:00+00:00",
            "mention_type": "STOCK",
            "subject": "OKLO",
            "sentiment": 64,
            "confidence": 82,
            "title": "Emerging energy opportunities",
            "event_type": "SECTOR_ATTENTION",
        },
        {
            "source_name": "Bow Tie Nation",
            "published_at": "2026-07-12T15:00:00+00:00",
            "mention_type": "THEME",
            "subject": "AI Infrastructure",
            "sentiment": 80,
            "confidence": 90,
        },
    ]


if __name__ == "__main__":
    build_and_write_research_intelligence(
        mentions=_sample_mentions(),
        internal_evidence_match={"OKLO": 68.0, "AI INFRASTRUCTURE": 84.0},
        as_of="2026-07-14T18:00:00+00:00",
    )
