"""Read Registry v2 artifact declarations as read-only strategy evidence.

This module never imports strategy plugin code, executes artifacts, changes
registry state, writes strategy files, moves capital, or contacts a broker.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

SUPPORTED_FORMATS = {"JSON", "CSV", "JSONL", "MARKDOWN", "HTML"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _plugins(registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    value = registry.get("strategy_plugins")
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _strategy_id(plugin: Mapping[str, Any]) -> str:
    return _text(plugin.get("strategy_id") or plugin.get("plugin_id") or plugin.get("service_id") or "UNKNOWN")


def _strategy_name(plugin: Mapping[str, Any]) -> str:
    return _text(plugin.get("display_name") or plugin.get("strategy_name") or plugin.get("name") or _strategy_id(plugin))


def _declared_artifacts(registry: Mapping[str, Any], plugin: Mapping[str, Any]) -> list[dict[str, Any]]:
    direct = plugin.get("dashboard_artifacts")
    if isinstance(direct, list):
        return [dict(item) for item in direct if isinstance(item, Mapping)]

    contracts = registry.get("strategy_contracts")
    if isinstance(contracts, Mapping):
        by_strategy = contracts.get("artifacts_by_strategy")
        if isinstance(by_strategy, Mapping):
            value = by_strategy.get(_strategy_id(plugin))
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def _resolve_path(path_text: str, *, root_dir: Path) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else root_dir / path


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl(path: Path) -> list[Any]:
    rows: list[Any] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        try:
            rows.append(json.loads(text))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at line {line_number}: {exc}") from exc
    return rows


def _read_artifact(path: Path, artifact_format: str) -> Any:
    normalized = artifact_format.upper()
    if normalized == "JSON":
        return _read_json(path)
    if normalized == "CSV":
        return _read_csv(path)
    if normalized == "JSONL":
        return _read_jsonl(path)
    if normalized in {"MARKDOWN", "HTML"}:
        return path.read_text(encoding="utf-8")
    raise ValueError(f"unsupported artifact format: {artifact_format}")


def load_registry_declared_evidence(
    registry: Mapping[str, Any],
    *,
    root_dir: str | Path = ".",
) -> tuple[list[dict[str, Any]], list[str]]:
    """Load plugin-declared artifacts and preserve explicit provenance.

    Optional missing or malformed artifacts produce warnings and remain visible in
    the returned strategy record. Required artifact failures mark the strategy
    evidence status as ``REQUIRED_EVIDENCE_MISSING`` but do not remove any other
    strategy from the result.
    """
    root = Path(root_dir)
    strategies: list[dict[str, Any]] = []
    warnings: list[str] = []

    for plugin in sorted(_plugins(registry), key=_strategy_id):
        strategy_id = _strategy_id(plugin)
        records: list[dict[str, Any]] = []
        required_failure = False

        for artifact in sorted(_declared_artifacts(registry, plugin), key=lambda item: _text(item.get("artifact_id"))):
            artifact_id = _text(artifact.get("artifact_id") or artifact.get("report_id") or artifact.get("id"))
            artifact_type = _text(artifact.get("artifact_type") or artifact.get("type") or artifact_id).upper()
            artifact_format = _text(artifact.get("format") or Path(_text(artifact.get("path"))).suffix.lstrip(".") or "JSON").upper()
            if artifact_format == "MD":
                artifact_format = "MARKDOWN"
            required = bool(artifact.get("required", False))
            authoritative = bool(artifact.get("authoritative", True))
            declared_path = _text(artifact.get("path") or artifact.get("report_path") or artifact.get("artifact_path"))
            path = _resolve_path(declared_path, root_dir=root)
            record: dict[str, Any] = {
                "artifact_id": artifact_id,
                "artifact_type": artifact_type,
                "format": artifact_format,
                "scope": _text(artifact.get("scope") or "STRATEGY").upper(),
                "declared_path": declared_path,
                "resolved_path": str(path),
                "required": required,
                "authoritative": authoritative,
                "read_only": True,
                "available": False,
                "payload": None,
                "provenance": {
                    "source_type": "PUBLISHED_ARTIFACT",
                    "source_id": str(path),
                    "authoritative": authoritative,
                    "reconstructed": False,
                },
            }

            if artifact_format not in SUPPORTED_FORMATS:
                warning = f"{strategy_id}:{artifact_id}: unsupported format {artifact_format}"
                record["error"] = warning
                warnings.append(warning)
                required_failure = required_failure or required
            elif not path.is_file():
                warning = f"{strategy_id}:{artifact_id}: declared artifact missing: {path}"
                record["error"] = warning
                warnings.append(warning)
                required_failure = required_failure or required
            else:
                try:
                    record["payload"] = _read_artifact(path, artifact_format)
                    record["available"] = True
                except (OSError, UnicodeError, json.JSONDecodeError, csv.Error, ValueError) as exc:
                    warning = f"{strategy_id}:{artifact_id}: invalid declared artifact {path}: {exc}"
                    record["error"] = warning
                    warnings.append(warning)
                    required_failure = required_failure or required
            records.append(record)

        available_count = sum(bool(item["available"]) for item in records)
        declared_count = len(records)
        if required_failure:
            evidence_status = "REQUIRED_EVIDENCE_MISSING"
        elif available_count == 0:
            evidence_status = "REGISTRY_ONLY"
        elif available_count < declared_count:
            evidence_status = "PARTIAL"
        else:
            evidence_status = "AVAILABLE"

        strategies.append({
            "strategy_id": strategy_id,
            "strategy_name": _strategy_name(plugin),
            "plugin_contract_version": _text(plugin.get("plugin_contract_version") or "1.0"),
            "evidence_status": evidence_status,
            "declared_artifact_count": declared_count,
            "available_artifact_count": available_count,
            "required_artifact_failure": required_failure,
            "artifacts": records,
        })

    return strategies, sorted(set(warnings))
