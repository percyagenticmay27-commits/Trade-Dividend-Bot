"""Generate a standalone read-only Enterprise portal staging preview."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from src.dividend_bot.enterprise_scan_first_ui import render_scan_first_dashboard

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _read_mapping(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required preview artifact not found: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Preview artifact root must be an object: {path}")
    return value


def _document(executive_html: str, investor_html: str) -> str:
    return f"""<!doctype html>
<html lang='en'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Enterprise Portal Preview</title>
<style>
body{{margin:0;background:#07111f;color:#e5edf8;font-family:Arial,sans-serif}}
.preview-banner{{position:sticky;top:0;z-index:9999;background:#f59e0b;color:#111827;padding:10px 18px;font-weight:700}}
.preview-nav{{display:flex;gap:10px;padding:12px 18px;background:#111827;position:sticky;top:39px;z-index:9998;border-bottom:1px solid #26364b}}
.preview-nav button{{border:1px solid #394d68;background:#17263a;color:#e8eef7;border-radius:8px;padding:10px 14px;cursor:pointer;font-weight:700}}
.preview-nav button.active{{background:#6d4aff;border-color:#8f78ff}}
.preview-page{{display:none}}
.preview-page.active{{display:block}}
</style>
</head>
<body>
<div class='preview-banner'>STAGING PREVIEW — PAPER ONLY — READ ONLY — NOT THE LIVE ALLOCATION PAGE</div>
<nav class='preview-nav'><button type='button' class='active' data-target='executive'>Executive Summary</button><button type='button' data-target='investor'>Investor Summary</button></nav>
<main>
<section id='executive' class='preview-page active'>{executive_html}</section>
<section id='investor' class='preview-page'>{investor_html}</section>
</main>
<script>
document.querySelectorAll('[data-target]').forEach(function(button){{button.addEventListener('click',function(){{document.querySelectorAll('.preview-page').forEach(function(page){{page.classList.remove('active')}});document.querySelectorAll('.preview-nav button').forEach(function(item){{item.classList.remove('active')}});document.getElementById(button.dataset.target).classList.add('active');button.classList.add('active');}})}});
</script>
</body></html>"""


def generate_enterprise_preview(*, results_dir: str | Path = "results") -> dict[str, Any]:
    directory = Path(results_dir)
    executive = _read_mapping(directory / "ai_cio_executive_dashboard.json")
    investor = _read_mapping(directory / "enterprise_investor_dashboard.json")
    html_path = directory / "enterprise-preview.html"
    status_path = directory / "enterprise-preview-status.json"
    html_path.write_text(
        _document(
            render_scan_first_dashboard(executive, audience="executive"),
            render_scan_first_dashboard(investor, audience="investor"),
        ),
        encoding="utf-8",
    )
    intelligence = executive.get("enterprise_dashboard_intelligence")
    if not isinstance(intelligence, Mapping):
        intelligence = {}
    status = {
        "schema_version": "1.1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "preview_ready": True,
        "layout": "SCAN_FIRST",
        "recommended_route": "/enterprise-preview",
        "registered_strategy_count": int(intelligence.get("registered_strategy_count", 0) or 0),
        "strategy_ids": list(intelligence.get("strategy_ids", [])) if isinstance(intelligence.get("strategy_ids"), list) else [],
        "executive_intelligence_attached": bool(executive.get("enterprise_dashboard_intelligence")),
        "investor_intelligence_attached": bool(investor.get("enterprise_dashboard_intelligence")),
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
        "read_only": True,
        "paths": {"preview_html": str(html_path), "status_json": str(status_path)},
    }
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the read-only Enterprise staging preview")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)
    try:
        status = generate_enterprise_preview(results_dir=args.results_dir)
    except Exception as exc:
        print(f"Enterprise preview generation failed: {exc}")
        return 1
    print(f"Preview HTML: {status['paths']['preview_html']}")
    print(f"Preview status: {status['paths']['status_json']}")
    print(f"Layout: {status['layout']}")
    print(f"Recommended route: {status['recommended_route']}")
    print("Strategy IDs: " + (", ".join(status["strategy_ids"]) or "none"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
