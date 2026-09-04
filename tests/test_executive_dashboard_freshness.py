from __future__ import annotations

import json
from pathlib import Path

from src.dividend_bot.portal_dashboard_routes import load_executive_dashboard_body


def test_executive_dashboard_prefers_fresh_json_over_existing_html(tmp_path: Path) -> None:
    html_path = tmp_path / "ai_cio_executive_dashboard.html"
    json_path = tmp_path / "ai_cio_executive_dashboard.json"

    html_path.write_text(
        "<!doctype html><html><body>STALE-SWING-WATCHLIST</body></html>",
        encoding="utf-8",
    )
    json_path.write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-09-04T17:00:00Z",
                "portfolio_summary": {"portfolio_value": 9500.0},
                "strategy_kpis": [],
            }
        ),
        encoding="utf-8",
    )

    body, served_static_html = load_executive_dashboard_body(
        html_path=html_path,
        json_path=json_path,
    )

    assert served_static_html is False
    assert "2026-09-04T17:00:00Z" in body
    assert "STALE-SWING-WATCHLIST" not in body
    assert "AI CIO Executive Dashboard" in body


def test_executive_dashboard_uses_html_only_when_json_is_missing(tmp_path: Path) -> None:
    html_path = tmp_path / "ai_cio_executive_dashboard.html"
    json_path = tmp_path / "ai_cio_executive_dashboard.json"
    html_path.write_text(
        "<!doctype html><html><body>HTML-FALLBACK</body></html>",
        encoding="utf-8",
    )

    body, served_static_html = load_executive_dashboard_body(
        html_path=html_path,
        json_path=json_path,
    )

    assert served_static_html is True
    assert "HTML-FALLBACK" in body
