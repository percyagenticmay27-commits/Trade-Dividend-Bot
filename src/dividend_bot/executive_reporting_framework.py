"""Shared presentation framework for Dividend executive reports.

Step 1 is presentation-only. It does not calculate portfolio values, alter pair
logic, change allocations, or execute trades.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Mapping

MODULE_NAME = "executive_reporting_framework"
MODULE_VERSION = "2.0.0"
REPORT_VERSION = "2.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

DEFAULT_PORTFOLIO_NAME = "TradeBot Dividend Paper Portfolio"
DEFAULT_STRATEGY_NAME = "Dividend ETF Strategy"
DEFAULT_STRATEGY_VERSION = "1.0"
DEFAULT_AI_CIO_VERSION = "Enterprise AI CIO"
DEFAULT_GENERATED_BY = "TradeBot Dividend Bot"

STANDARD_SECTION_ORDER = (
    "Executive Summary",
    "Portfolio Summary",
    "Report Details",
    "Analysis",
    "Recommendations",
    "Alerts",
    "Final Assessment",
)


@dataclass(frozen=True)
class ReportDefinition:
    report_name: str
    what_it_shows: str
    why_it_is_used: str


REPORT_DEFINITIONS: Mapping[str, ReportDefinition] = {
    "daily_paper_report.md": ReportDefinition(
        report_name="Daily Paper Report",
        what_it_shows=(
            "The complete daily paper-trading portfolio, including capital allocation, "
            "active ETF pairs, funds held in SGOV, portfolio value, dividends, and "
            "current recommendations."
        ),
        why_it_is_used=(
            "To provide a complete daily record of where portfolio capital is allocated "
            "and verify that the paper portfolio is consistently reported without "
            "executing real trades."
        ),
    ),
    "daily_change_summary.md": ReportDefinition(
        report_name="Daily Change Summary",
        what_it_shows=(
            "Changes since the previous completed trading cycle, including signals, "
            "pair changes, SGOV movements, dividends, earnings events, and next-day "
            "recommendations."
        ),
        why_it_is_used=(
            "To let operators and the AI CIO identify new events and decisions without "
            "reviewing the entire portfolio history."
        ),
    ),
    "strategy_health_report.md": ReportDefinition(
        report_name="Strategy Health Report",
        what_it_shows=(
            "The financial and operational health of the Dividend Strategy, including "
            "accounting consistency, performance indicators, pair stability, drawdown, "
            "and validation checks."
        ),
        why_it_is_used=(
            "To confirm that the strategy is operating consistently and identify issues "
            "that require review during paper validation."
        ),
    ),
    "live_readiness_report.md": ReportDefinition(
        report_name="Live Readiness Report",
        what_it_shows=(
            "Progress through paper-trading validation milestones and operational "
            "readiness checks required before any future production review."
        ),
        why_it_is_used=(
            "To prevent the strategy from being treated as production-ready before it "
            "has accumulated sufficient validated paper-trading evidence."
        ),
    ),
}


def report_definition(source_name: str) -> ReportDefinition:
    try:
        return REPORT_DEFINITIONS[source_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported executive report source: {source_name}") from exc


def executive_metadata(
    *,
    source_name: str,
    trading_date: date,
    generated_at: datetime | None = None,
    portfolio_name: str = DEFAULT_PORTFOLIO_NAME,
    strategy_name: str = DEFAULT_STRATEGY_NAME,
    strategy_version: str = DEFAULT_STRATEGY_VERSION,
    ai_cio_version: str = DEFAULT_AI_CIO_VERSION,
) -> dict[str, Any]:
    definition = report_definition(source_name)
    generated = generated_at or datetime.now(timezone.utc)
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    return {
        "report_name": definition.report_name,
        "report_version": REPORT_VERSION,
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "trading_date": trading_date.isoformat(),
        "portfolio_name": portfolio_name,
        "paper_trading_mode": True,
        "strategy_name": strategy_name,
        "strategy_version": strategy_version,
        "ai_cio_version": ai_cio_version,
        "generated_by": DEFAULT_GENERATED_BY,
        "what_this_report_shows": definition.what_it_shows,
        "why_this_report_is_used": definition.why_it_is_used,
        "standard_section_order": " | ".join(STANDARD_SECTION_ORDER),
        "safety_statement": "PAPER ONLY - NO REAL TRADES EXECUTED",
    }


def executive_framework_rows(
    *,
    source_name: str,
    trading_date: date,
    generated_at: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return ordered presentation rows for use by CSV report writers."""
    metadata = executive_metadata(
        source_name=source_name,
        trading_date=trading_date,
        generated_at=generated_at,
    )
    rows: list[dict[str, Any]] = []
    ordered_fields = (
        ("Executive Header", "Report Name", metadata["report_name"]),
        ("Executive Header", "Report Version", metadata["report_version"]),
        ("Executive Header", "Generated At", metadata["generated_at"]),
        ("Executive Header", "Trading Date", metadata["trading_date"]),
        ("Executive Header", "Portfolio", metadata["portfolio_name"]),
        ("Executive Header", "Paper Trading Mode", metadata["paper_trading_mode"]),
        ("Executive Header", "Strategy", metadata["strategy_name"]),
        ("Executive Header", "Strategy Version", metadata["strategy_version"]),
        ("Executive Header", "AI CIO Version", metadata["ai_cio_version"]),
        ("Executive Header", "Generated By", metadata["generated_by"]),
        ("What This Report Shows", "Purpose", metadata["what_this_report_shows"]),
        ("Why This Report Is Used", "Use", metadata["why_this_report_is_used"]),
        ("Executive Standard", "Section Order", metadata["standard_section_order"]),
        ("Executive Footer", "Safety", metadata["safety_statement"]),
    )
    for section, field, value in ordered_fields:
        rows.append({"section": section, "field": field, "value": value})
    return rows
