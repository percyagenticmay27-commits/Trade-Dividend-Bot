"""Generate read-only static HTML dashboards from existing Dividend Bot JSON reports."""
from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

MODULE_NAME = "enterprise_html_dashboard"
MODULE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

DEFAULT_REPORTS = (
    ("Executive Dashboard", "enterprise_dividend_dashboard.json", "executive_dashboard.html"),
    ("Investor Dashboard", "enterprise_investor_dashboard.json", "investor_dashboard.html"),
    ("Strategy Health", "enterprise_dividend_strategy_health.json", "strategy_health.html"),
    ("CIO Advisory", "enterprise_dividend_cio_advisory.json", "cio_advisory.html"),
    ("Learning", "enterprise_dividend_learning.json", "learning.html"),
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _label(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _metric_cards(summary: Mapping[str, Any]) -> str:
    cards = []
    for key, value in list(summary.items())[:10]:
        if isinstance(value, (dict, list)):
            continue
        cards.append(
            '<article class="metric-card">'
            f'<div class="metric-label">{html.escape(_label(str(key)))}</div>'
            f'<div class="metric-value">{html.escape(_display(value))}</div>'
            '<button type="button" class="more" aria-label="Show metric details">…more</button>'
            '</article>'
        )
    return "".join(cards) or '<article class="metric-card"><div class="metric-label">Status</div><div class="metric-value">No summary data</div></article>'


def _table_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return '<p class="empty">No records available.</p>'
    columns = []
    for row in rows:
        for key in row:
            if key not in columns and not isinstance(row.get(key), (dict, list)):
                columns.append(key)
    columns = columns[:6]
    head = "".join(f"<th>{html.escape(_label(str(column)))}</th>" for column in columns)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(_display(row.get(column)))}</td>" for column in columns) + "</tr>"
        for row in rows[:25]
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def render_dashboard_html(
    *,
    title: str,
    report: Mapping[str, Any],
    navigation: Sequence[tuple[str, str]],
    generated_at_utc: Optional[str] = None,
) -> str:
    generated = generated_at_utc or str(report.get("generated_at_utc") or _now_utc())
    summary = report.get("summary") if isinstance(report.get("summary"), Mapping) else {}
    rows = []
    for key in ("alerts", "reviews", "recommendations", "learning_records", "risk_flags", "holdings", "positions"):
        value = report.get(key)
        if isinstance(value, list) and value and isinstance(value[0], Mapping):
            rows = value
            break
    nav = "".join(f'<a href="{html.escape(href)}">{html.escape(label)}</a>' for label, href in navigation)
    status = report.get("status") or report.get("advisory_status") or report.get("workflow_status") or "READY"
    commentary = report.get("executive_summary") or report.get("ai_cio_commentary") or report.get("commentary")
    if not commentary:
        commentary = "This page presents a read-only paper-trading snapshot generated from the latest governed report artifact."
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root{{--navy:#081a39;--purple:#5d18d6;--line:#dfe3ec;--muted:#667085;--bg:#f5f7fb}}
*{{box-sizing:border-box}}body{{margin:0;font-family:Arial,Helvetica,sans-serif;background:var(--bg);color:#101828}}
header{{background:linear-gradient(120deg,#07172f,#10244b);color:white;padding:24px 32px}}header h1{{margin:0;font-size:30px}}header p{{margin:8px 0 0}}
nav{{display:flex;gap:18px;flex-wrap:wrap;padding:12px 32px;background:white;border-bottom:1px solid var(--line)}}nav a{{color:#344054;text-decoration:none;font-weight:700}}
.banner{{margin:18px 24px;padding:12px 16px;border-left:5px solid var(--purple);background:#f1eaff;font-weight:700}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px;padding:0 24px 18px}}
.metric-card,.panel{{background:white;border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 14px rgba(16,24,40,.05)}}.metric-card{{padding:20px;min-height:145px}}
.metric-label{{font-weight:700}}.metric-value{{font-size:28px;font-weight:800;color:var(--purple);margin:22px 0 14px}}.more{{border:0;background:none;color:#1665d8;cursor:pointer}}
.content{{display:grid;grid-template-columns:minmax(280px,.8fr) minmax(420px,1.4fr);gap:18px;padding:0 24px 28px}}.panel{{padding:22px}}.panel h2{{margin-top:0;color:#43169a}}
.detail{{display:grid;grid-template-columns:170px 1fr;gap:15px;padding:16px 0;border-bottom:1px solid var(--line)}}.detail strong{{color:#344054}}
.commentary{{background:#fffaf0;border:1px solid #f4cc73;border-radius:12px;padding:18px;line-height:1.55}}
.table-wrap{{overflow:auto}}table{{width:100%;border-collapse:collapse}}th{{background:#43169a;color:white}}th,td{{padding:10px;border:1px solid var(--line);text-align:left}}
footer{{padding:18px 24px 30px;color:var(--muted);font-size:13px}}@media(max-width:850px){{.content{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>{html.escape(title)}</h1><p>Enterprise AI CIO paper-only reporting portal</p></header>
<nav>{nav}</nav>
<div class="banner">PAPER ONLY · No live orders · No brokerage communication · Investor approval required · Status: {html.escape(str(status))}</div>
<section class="grid">{_metric_cards(summary)}</section>
<section class="content">
<article class="panel"><h2>Metric Guide</h2>
<div class="detail"><strong>What is this?</strong><span>A governed snapshot of the latest {html.escape(title.lower())} report.</span></div>
<div class="detail"><strong>How is it calculated?</strong><span>Values are read directly from the existing JSON report produced by the Dividend Bot.</span></div>
<div class="detail"><strong>Why does it matter?</strong><span>It gives the investor a consistent executive view without authorizing any trade or capital movement.</span></div>
<div class="detail"><strong>Is this estimated?</strong><span>Some forecast, protection, confidence, and replacement values may be estimates. Actual paper outcomes may differ.</span></div>
<div class="detail"><strong>Measurement period</strong><span>{html.escape(str(report.get('reporting_period') or report.get('generated_at_utc') or generated))}</span></div>
</article>
<article class="panel"><h2>Current Contributors</h2>{_table_rows(rows)}
<h2 style="margin-top:22px">AI CIO Commentary</h2><div class="commentary">{html.escape(str(commentary))}</div></article>
</section>
<footer>Generated {html.escape(generated)} · Module {MODULE_NAME} v{MODULE_VERSION} · Read-only static HTML hosted on DigitalOcean.</footer>
</body></html>"""


def build_html_portal(
    *,
    reports_dir: str | Path = "results",
    output_dir: str | Path = "results/html",
    report_specs: Sequence[tuple[str, str, str]] = DEFAULT_REPORTS,
    generated_at_utc: Optional[str] = None,
) -> dict[str, Any]:
    source = Path(reports_dir)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    navigation = [(title, filename) for title, _, filename in report_specs]
    generated_pages = []
    warnings = []
    for title, source_name, output_name in report_specs:
        report_path = source / source_name
        report = _load_json(report_path)
        if not report:
            warnings.append(f"Missing or empty source report: {report_path}")
        html_text = render_dashboard_html(title=title, report=report, navigation=navigation, generated_at_utc=generated_at_utc)
        page_path = destination / output_name
        page_path.write_text(html_text, encoding="utf-8")
        generated_pages.append({"title": title, "path": str(page_path), "source": str(report_path)})
    index_cards = "".join(f'<li><a href="{html.escape(filename)}">{html.escape(title)}</a></li>' for title, _, filename in report_specs)
    index = f"<!doctype html><html lang='en'><meta charset='utf-8'><title>AI CIO Portal</title><body><h1>AI CIO Dividend Portal</h1><p><strong>PAPER ONLY</strong></p><ul>{index_cards}</ul></body></html>"
    (destination / "index.html").write_text(index, encoding="utf-8")
    return {
        "module_name": MODULE_NAME,
        "module_version": MODULE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "output_dir": str(destination),
        "index_path": str(destination / "index.html"),
        "generated_pages": generated_pages,
        "warnings": warnings,
    }
