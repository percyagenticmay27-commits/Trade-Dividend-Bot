"""Standalone operator evidence page for unified dashboard cycle acceptance."""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
from typing import Any, Mapping

MODULE_NAME = "enterprise_unified_dashboard_acceptance_renderer"
MODULE_VERSION = "1.0.0"

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False
REPORTING_ONLY = True


def _read_mapping(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Acceptance evidence root must be an object: {path}")
    return payload


def load_acceptance_evidence(results_dir: str | Path) -> dict[str, dict[str, Any]]:
    directory = Path(results_dir)
    return {
        "acceptance": _read_mapping(
            directory / "enterprise_unified_dashboard_cycle_acceptance.json"
        ),
        "cycle": _read_mapping(directory / "enterprise_unified_dashboard_cycle.json"),
        "validation": _read_mapping(
            directory / "enterprise_unified_dashboard_validation.json"
        ),
    }


def build_acceptance_view_model(
    *,
    acceptance: Mapping[str, Any],
    cycle: Mapping[str, Any],
    validation: Mapping[str, Any],
) -> dict[str, Any]:
    """Cross-check acceptance evidence before rendering the operator view."""
    errors: list[str] = []
    warnings: list[str] = []
    expected_statuses = (
        ("acceptance", acceptance.get("acceptance_status")),
        ("cycle", cycle.get("cycle_status")),
        ("validation", validation.get("validation_status")),
    )
    for name, status in expected_statuses:
        if status != "PASSED":
            errors.append(f"{name} status is not PASSED: {status or 'MISSING'}")

    expected_safety = {
        "paper_trade_mode": True,
        "live_trading_enabled": False,
        "broker_execution_enabled": False,
        "capital_movement_enabled": False,
        "reporting_only": True,
    }
    for document_name, document in (("acceptance", acceptance), ("cycle", cycle)):
        for field, expected in expected_safety.items():
            if document.get(field) is not expected:
                errors.append(f"{document_name} safety field {field} must be {expected}")

    required_ids = acceptance.get("required_strategy_ids")
    required = sorted(
        {
            str(item).strip()
            for item in required_ids
            if str(item).strip()
        }
    ) if isinstance(required_ids, list) else []
    summaries = validation.get("strategy_kpi_summary")
    kpi_summary = summaries if isinstance(summaries, Mapping) else {}
    for strategy_id in required:
        if strategy_id not in kpi_summary:
            errors.append(f"Required strategy is missing from validation: {strategy_id}")

    for document in (acceptance, cycle, validation):
        values = document.get("warnings")
        if isinstance(values, list):
            warnings.extend(str(item) for item in values if str(item).strip())
        values = document.get("errors")
        if isinstance(values, list):
            errors.extend(str(item) for item in values if str(item).strip())

    manifest = acceptance.get("artifact_manifest")
    artifact_manifest = manifest if isinstance(manifest, Mapping) else {}
    return {
        "verification_status": "PASSED" if not errors else "FAILED",
        "acceptance_status": str(acceptance.get("acceptance_status") or "UNKNOWN"),
        "cycle_status": str(cycle.get("cycle_status") or "UNKNOWN"),
        "validation_status": str(validation.get("validation_status") or "UNKNOWN"),
        "generated_at_utc": str(acceptance.get("generated_at_utc") or ""),
        "protected_state_unchanged": acceptance.get("protected_state_unchanged") is True,
        "protected_state_file_count": int(
            acceptance.get("protected_state_file_count", 0) or 0
        ),
        "required_strategy_ids": required,
        "strategy_kpi_summary": {
            strategy_id: dict(kpi_summary[strategy_id])
            for strategy_id in required
            if isinstance(kpi_summary.get(strategy_id), Mapping)
        },
        "artifact_manifest": {
            str(name): dict(entry)
            for name, entry in artifact_manifest.items()
            if isinstance(entry, Mapping)
        },
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        **expected_safety,
    }


def _status(value: Any) -> str:
    return escape(str(value or "UNKNOWN"))


def _render_messages(values: list[str], empty: str) -> str:
    if not values:
        return f'<li class="empty">{escape(empty)}</li>'
    return "".join(f"<li>{escape(item)}</li>" for item in values)


def _render_strategy_rows(model: Mapping[str, Any]) -> str:
    summaries = model.get("strategy_kpi_summary")
    if not isinstance(summaries, Mapping) or not summaries:
        return '<tr><td colspan="5">No strategy validation evidence reported.</td></tr>'
    rows: list[str] = []
    for strategy_id, raw in summaries.items():
        summary = raw if isinstance(raw, Mapping) else {}
        rows.append(
            "<tr>"
            f"<td><strong>{escape(str(strategy_id))}</strong></td>"
            f"<td>{_status(summary.get('health_status'))}</td>"
            f"<td>{escape(str(summary.get('allocated_capital', 'Not reported')))}</td>"
            f"<td>{_status(summary.get('evidence_status'))}</td>"
            f"<td>{_status(summary.get('decision_journal_status'))}</td>"
            "</tr>"
        )
    return "".join(rows)


def _render_artifact_rows(model: Mapping[str, Any]) -> str:
    manifest = model.get("artifact_manifest")
    if not isinstance(manifest, Mapping) or not manifest:
        return '<tr><td colspan="4">No artifact evidence reported.</td></tr>'
    rows: list[str] = []
    for name, raw in sorted(manifest.items()):
        entry = raw if isinstance(raw, Mapping) else {}
        safe_name = Path(str(name)).name
        digest = str(entry.get("sha256") or "Not reported")
        rows.append(
            "<tr>"
            f'<td><a href="{escape(safe_name, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer">{escape(str(name))}</a></td>'
            f"<td>{escape(str(entry.get('size_bytes', 0)))}</td>"
            f"<td>{escape(digest)}</td>"
            f"<td>{'YES' if entry.get('exists') is True else 'NO'}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_acceptance_evidence_document(model: Mapping[str, Any]) -> str:
    verification = _status(model.get("verification_status"))
    state_status = "UNCHANGED" if model.get("protected_state_unchanged") is True else "CHANGED"
    errors = model.get("errors") if isinstance(model.get("errors"), list) else []
    warnings = model.get("warnings") if isinstance(model.get("warnings"), list) else []
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Enterprise Unified Dashboard Acceptance</title>
<style>
:root{{--ink:#101828;--muted:#667085;--line:#dbe3ef;--paper:#fff;--bg:#f5f7fb;--violet:#5b21b6;--green:#067647;--red:#b42318}}
*{{box-sizing:border-box}}body{{margin:0;padding:24px;background:var(--bg);color:var(--ink);font-family:Arial,sans-serif}}main{{max-width:1400px;margin:auto}}
.hero,.panel{{background:var(--paper);border:1px solid var(--line);border-radius:16px;padding:20px;margin-bottom:16px}}.hero{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}}
.eyebrow{{color:var(--violet);font-size:12px;font-weight:800}}.badges{{display:flex;gap:8px;flex-wrap:wrap}}.badge{{border-radius:999px;padding:7px 10px;background:#eef2ff;font-size:12px;font-weight:800}}
.status-PASSED{{color:var(--green);background:#ecfdf3}}.status-FAILED,.status-CHANGED{{color:var(--red);background:#fef3f2}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metric{{background:#f8fafc;border:1px solid var(--line);border-radius:12px;padding:14px}}.metric span{{display:block;color:var(--muted);font-size:12px}}.metric strong{{display:block;margin-top:7px}}
table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #e5e7eb;vertical-align:top}}th{{color:var(--muted);font-size:12px}}td:nth-child(3){{font-family:monospace;word-break:break-all}}a{{color:var(--violet)}}.messages{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}.empty{{color:var(--muted)}}@media(max-width:800px){{.hero{{display:block}}.grid{{grid-template-columns:1fr 1fr}}.messages{{grid-template-columns:1fr}}}}@media(max-width:480px){{body{{padding:12px}}.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="hero"><div><p class="eyebrow">ENTERPRISE AI CIO · PAPER ONLY · READ ONLY</p><h1>Unified Dashboard Acceptance Evidence</h1><p>Generated {escape(str(model.get('generated_at_utc') or 'Not reported'))}</p></div>
<div class="badges"><span class="badge status-{verification}">VERIFICATION {verification}</span><span class="badge">NO BROKER EXECUTION</span><span class="badge">NO CAPITAL MOVEMENT</span></div></section>
<section class="panel grid">
<div class="metric"><span>Acceptance</span><strong>{_status(model.get('acceptance_status'))}</strong></div>
<div class="metric"><span>Cycle</span><strong>{_status(model.get('cycle_status'))}</strong></div>
<div class="metric"><span>Validation</span><strong>{_status(model.get('validation_status'))}</strong></div>
<div class="metric"><span>Protected state</span><strong class="status-{state_status}">{state_status}</strong></div>
</section>
<section class="panel"><h2>Strategy Validation</h2><table><thead><tr><th>Strategy</th><th>Health</th><th>Allocated capital</th><th>Evidence</th><th>Decision journal</th></tr></thead><tbody>{_render_strategy_rows(model)}</tbody></table></section>
<section class="panel"><h2>Artifact Integrity Evidence</h2><table><thead><tr><th>Artifact</th><th>Bytes</th><th>SHA-256</th><th>Exists</th></tr></thead><tbody>{_render_artifact_rows(model)}</tbody></table></section>
<section class="panel messages"><div><h2>Errors</h2><ul>{_render_messages(errors, 'None')}</ul></div><div><h2>Warnings</h2><ul>{_render_messages(warnings, 'None')}</ul></div></section>
</main></body></html>'''


def generate_acceptance_evidence_preview(
    *, results_dir: str | Path = "results", output_path: str | Path | None = None
) -> dict[str, Any]:
    directory = Path(results_dir)
    evidence = load_acceptance_evidence(directory)
    model = build_acceptance_view_model(**evidence)
    output = (
        Path(output_path)
        if output_path is not None
        else directory / "enterprise-unified-dashboard-acceptance.html"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_acceptance_evidence_document(model), encoding="utf-8")
    return {"path": str(output), "verification_status": model["verification_status"]}
