"""Market Intelligence Center for the paper-only AI CIO.

Combines regime, breadth, volatility, macro, news, sector context, and portfolio
implications into one read-only market briefing. Sector information is context
only and never creates capital entitlement or overrides opportunity ranking.
"""
from __future__ import annotations

import html
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "market_intelligence_center"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
REPORTING_ONLY = True

DEFAULT_OUTPUT_FILES = {
    "json": "market_intelligence_center.json",
    "markdown": "market_intelligence_center.md",
    "html": "market_intelligence_center.html",
}

DETAILS = {
    "market_regime": {
        "label": "Market Regime",
        "definition": "The broad environment inferred from trend, breadth, volatility, liquidity, and risk appetite.",
        "calculation": "Uses supplied regime evidence and supporting market indicators.",
        "why_it_matters": "The regime changes how strongly the AI CIO interprets risk and opportunity evidence, but it does not select investments by itself.",
    },
    "market_breadth": {
        "label": "Market Breadth",
        "definition": "Measures how widely gains or losses are distributed across the market.",
        "calculation": "Combines advancing-share percentage, new highs versus lows, and supplied breadth scores.",
        "why_it_matters": "A rally supported by many securities is usually healthier than one driven by only a few names.",
    },
    "volatility": {
        "label": "Volatility",
        "definition": "Measures the current level and direction of market price variability.",
        "calculation": "Uses supplied volatility level, trend, and percentile values.",
        "why_it_matters": "Higher volatility can increase drawdown, gap, and path-dependency risk.",
    },
    "macro_context": {
        "label": "Macro Context",
        "definition": "Summarizes interest-rate, inflation, labor, liquidity, and economic-growth evidence.",
        "calculation": "Normalizes supplied macro signals to a common score from -100 to +100.",
        "why_it_matters": "Macro conditions can strengthen or weaken the environment supporting individual opportunities.",
    },
    "news_sentiment": {
        "label": "News Sentiment",
        "definition": "Summarizes the direction and confidence of current market-relevant news.",
        "calculation": "Weights supplied news items by sentiment, confidence, freshness, and relevance.",
        "why_it_matters": "News can change expectations before those changes appear in price or fundamentals.",
    },
    "sector_context": {
        "label": "Sector Context",
        "definition": "Shows which sectors have stronger or weaker current evidence.",
        "calculation": "Ranks sector evidence using supplied strength, momentum, news, and regime-support scores.",
        "why_it_matters": "Sector context can support or challenge an opportunity, but it never guarantees capital or creates a quota.",
    },
    "portfolio_implications": {
        "label": "Portfolio Implications",
        "definition": "Explains how current market evidence may affect existing portfolio reviews.",
        "calculation": "Maps the market briefing to supplied portfolio exposures and active lifecycle states.",
        "why_it_matters": "It turns broad market evidence into practical context while leaving allocation decisions to the opportunity and decision engines.",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _number(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _clamp(value: Any, minimum: float = -100.0, maximum: float = 100.0) -> float:
    return round(max(minimum, min(maximum, _number(value))), 4)


def _label(score: float) -> str:
    score = _clamp(score)
    if score >= 60:
        return "STRONGLY_SUPPORTIVE"
    if score >= 20:
        return "SUPPORTIVE"
    if score > -20:
        return "NEUTRAL"
    if score > -60:
        return "CAUTIOUS"
    return "DEFENSIVE"


def _normalize_news(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    weighted = 0.0
    total_weight = 0.0
    normalized = []
    for row in items or []:
        if not isinstance(row, Mapping):
            continue
        sentiment = _clamp(row.get("sentiment_score", row.get("sentiment", 0.0)))
        confidence = max(0.0, min(100.0, _number(row.get("confidence", 50.0)))) / 100.0
        relevance = max(0.0, min(100.0, _number(row.get("relevance", 50.0)))) / 100.0
        freshness = max(0.0, min(100.0, _number(row.get("freshness", 100.0)))) / 100.0
        weight = confidence * relevance * freshness
        weighted += sentiment * weight
        total_weight += weight
        normalized.append({
            "headline": str(row.get("headline") or row.get("title") or "Untitled"),
            "sentiment_score": sentiment,
            "confidence": round(confidence * 100.0, 2),
            "relevance": round(relevance * 100.0, 2),
            "freshness": round(freshness * 100.0, 2),
        })
    score = weighted / total_weight if total_weight else 0.0
    return {"score": _clamp(score), "label": _label(score), "items": normalized}


def _normalize_sectors(items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    sectors = []
    for row in items or []:
        if not isinstance(row, Mapping):
            continue
        scores = [
            _clamp(row.get("strength_score", 0.0)),
            _clamp(row.get("momentum_score", 0.0)),
            _clamp(row.get("news_score", 0.0)),
            _clamp(row.get("regime_support_score", 0.0)),
        ]
        score = round(sum(scores) / len(scores), 4)
        sectors.append({
            "sector": str(row.get("sector") or "UNKNOWN").upper(),
            "context_score": score,
            "context_label": _label(score),
            "allocation_authority": False,
        })
    return sorted(sectors, key=lambda item: item["context_score"], reverse=True)


def build_market_intelligence_center(
    *,
    market_regime: Optional[Mapping[str, Any]] = None,
    breadth: Optional[Mapping[str, Any]] = None,
    volatility: Optional[Mapping[str, Any]] = None,
    macro_signals: Optional[Sequence[Mapping[str, Any]]] = None,
    news_items: Optional[Sequence[Mapping[str, Any]]] = None,
    sector_evidence: Optional[Sequence[Mapping[str, Any]]] = None,
    portfolio_exposures: Optional[Sequence[Mapping[str, Any]]] = None,
) -> dict[str, Any]:
    """Build the read-only Market Intelligence Center report."""
    warnings: list[str] = []
    regime = dict(market_regime or {})
    regime_score = _clamp(regime.get("score", regime.get("regime_score", 0.0)))
    regime_label = str(regime.get("label") or regime.get("regime") or _label(regime_score)).upper()

    breadth_data = dict(breadth or {})
    breadth_values = [
        _clamp(breadth_data.get("breadth_score", 0.0)),
        _clamp((_number(breadth_data.get("advancing_percent", 50.0)) - 50.0) * 2.0),
        _clamp(_number(breadth_data.get("new_highs", 0.0)) - _number(breadth_data.get("new_lows", 0.0))),
    ]
    breadth_score = round(sum(breadth_values) / len(breadth_values), 4)

    vol = dict(volatility or {})
    vol_percentile = max(0.0, min(100.0, _number(vol.get("percentile", 50.0))))
    vol_trend = str(vol.get("trend") or "STABLE").upper()
    volatility_score = _clamp(50.0 - vol_percentile)

    macro_rows = []
    for row in macro_signals or []:
        if isinstance(row, Mapping):
            macro_rows.append({"name": str(row.get("name") or "Macro Signal"), "score": _clamp(row.get("score", 0.0))})
    macro_score = round(sum(item["score"] for item in macro_rows) / len(macro_rows), 4) if macro_rows else 0.0

    news = _normalize_news(news_items or [])
    sectors = _normalize_sectors(sector_evidence or [])

    components = {
        "market_regime": regime_score,
        "market_breadth": breadth_score,
        "volatility": volatility_score,
        "macro_context": macro_score,
        "news_sentiment": news["score"],
    }
    weights = {"market_regime": 0.30, "market_breadth": 0.20, "volatility": 0.15, "macro_context": 0.20, "news_sentiment": 0.15}
    overall = round(sum(components[key] * weights[key] for key in weights), 4)

    exposures = []
    for row in portfolio_exposures or []:
        if isinstance(row, Mapping):
            exposures.append({
                "allocation": str(row.get("allocation") or row.get("allocation_id") or "UNKNOWN"),
                "sector": str(row.get("sector") or row.get("sector_context") or "UNKNOWN").upper(),
                "allocation_percent": max(0.0, _number(row.get("allocation_percent", 0.0))),
            })

    if not regime:
        warnings.append("Market regime evidence was not supplied; regime defaults to neutral.")
    if not news_items:
        warnings.append("No news items were supplied; News Sentiment defaults to neutral.")

    leader = sectors[0]["sector"] if sectors else "No sector leader available"
    commentary = (
        f"The current market environment is {_label(overall).replace('_', ' ').title()} with an overall score of {overall:.2f}. "
        f"The reported regime is {regime_label.replace('_', ' ').title()}, breadth is {_label(breadth_score).replace('_', ' ').title()}, "
        f"and volatility is {vol_trend.replace('_', ' ').title()}. The strongest sector context is {leader}. "
        "Sector evidence remains supporting context only; every stock, fund, pair, or strategy must independently earn capital through the opportunity-ranking process."
    )

    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "reporting_only": True,
        "overall_market_intelligence_score": overall,
        "overall_market_intelligence_label": _label(overall),
        "market_regime": {"score": regime_score, "label": regime_label, "source": regime},
        "market_breadth": {"score": breadth_score, "label": _label(breadth_score), "source": breadth_data},
        "volatility": {"score": volatility_score, "label": _label(volatility_score), "percentile": vol_percentile, "trend": vol_trend},
        "macro_context": {"score": macro_score, "label": _label(macro_score), "signals": macro_rows},
        "news_sentiment": news,
        "sector_context": sectors,
        "portfolio_implications": {"exposures": exposures, "allocation_authority": False},
        "component_weights": weights,
        "details": DETAILS,
        "ai_cio_commentary": commentary,
        "warnings": warnings,
        "errors": [],
    }


def format_market_intelligence_markdown(report: Mapping[str, Any]) -> str:
    lines = [
        "# Market Intelligence Center",
        "",
        "## Executive Summary",
        "",
        f"- **Overall Market Intelligence:** {str(report.get('overall_market_intelligence_label', 'NEUTRAL')).replace('_', ' ').title()} ({_number(report.get('overall_market_intelligence_score')):.2f} / 100)",
        f"- **Market Regime:** {str((report.get('market_regime') or {}).get('label', 'UNKNOWN')).replace('_', ' ').title()}",
        f"- **Market Breadth:** {str((report.get('market_breadth') or {}).get('label', 'NEUTRAL')).replace('_', ' ').title()}",
        f"- **Volatility:** {str((report.get('volatility') or {}).get('trend', 'STABLE')).replace('_', ' ').title()}",
        "",
        "## Sector Context",
        "",
        "| Rank | Sector | Context Score | Context | Allocation Authority |",
        "|---:|---|---:|---|---|",
    ]
    for index, item in enumerate(report.get("sector_context") or [], start=1):
        lines.append(f"| {index} | {item['sector']} | {item['context_score']:.2f} | {item['context_label'].replace('_', ' ').title()} | No |")
    lines.extend(["", "## AI CIO Commentary", "", str(report.get("ai_cio_commentary", "No commentary available.")), "", "## Metric Reference", ""])
    for key, detail in DETAILS.items():
        lines.extend([
            f"### {detail['label']}", "",
            f"**What it means:** {detail['definition']}", "",
            f"**How it is calculated:** {detail['calculation']}", "",
            f"**Why it matters:** {detail['why_it_matters']}", "",
        ])
    lines.extend(["## Paper-Only Safety", "", "This report is read-only. It does not place orders, communicate with a brokerage, create sector quotas, or override opportunity rankings.", ""])
    return "\n".join(lines)


def format_market_intelligence_html(report: Mapping[str, Any]) -> str:
    escaped = html.escape(format_market_intelligence_markdown(report))
    return "<!doctype html><html><head><meta charset='utf-8'><title>Market Intelligence Center</title><style>body{font-family:Arial,sans-serif;max-width:1200px;margin:auto;padding:32px;background:#f5f7fb;color:#172033}pre{white-space:pre-wrap;background:#fff;padding:28px;border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);line-height:1.5}</style></head><body><pre>" + escaped + "</pre></body></html>"


def write_market_intelligence_center(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    report = build_market_intelligence_center(**dict(payload))
    root = Path(root_path)
    files = dict(DEFAULT_OUTPUT_FILES)
    if output_files:
        files.update(output_files)
    (root / files["json"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / files["markdown"]).write_text(format_market_intelligence_markdown(report), encoding="utf-8")
    (root / files["html"]).write_text(format_market_intelligence_html(report), encoding="utf-8")
    return report


def build_and_write_market_intelligence_center(payload: Mapping[str, Any], root_path: str = ".", output_files: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
    return write_market_intelligence_center(payload, root_path, output_files)


if __name__ == "__main__":
    sample = {
        "market_regime": {"label": "BULL", "score": 55},
        "breadth": {"breadth_score": 42, "advancing_percent": 61, "new_highs": 85, "new_lows": 24},
        "volatility": {"percentile": 38, "trend": "STABLE"},
        "macro_signals": [{"name": "Liquidity", "score": 30}, {"name": "Rates", "score": -10}],
        "news_items": [{"headline": "Technology earnings remain resilient", "sentiment_score": 45, "confidence": 90, "relevance": 85, "freshness": 95}],
        "sector_evidence": [
            {"sector": "Technology", "strength_score": 70, "momentum_score": 65, "news_score": 55, "regime_support_score": 60},
            {"sector": "Healthcare", "strength_score": 45, "momentum_score": 35, "news_score": 20, "regime_support_score": 30},
        ],
    }
    result = write_market_intelligence_center(sample)
    print(f"Market Intelligence: {result['overall_market_intelligence_score']:.2f} / 100")
