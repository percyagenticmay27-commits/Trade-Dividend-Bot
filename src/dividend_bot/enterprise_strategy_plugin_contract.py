"""Registry v2 contract for Enterprise AI CIO strategy plugins.

This module validates declarative plugin metadata only. It never imports plugin
production code, reads plugin artifacts, invokes trading logic, contacts a
broker, or moves capital.
"""
from __future__ import annotations

from pathlib import PurePath
from typing import Any, Mapping, Sequence

PLUGIN_CONTRACT_VERSION = "2.0"
SUPPORTED_ARTIFACT_FORMATS = {"JSON", "CSV", "MARKDOWN", "HTML", "JSONL"}
SUPPORTED_ARTIFACT_SCOPES = {"STRATEGY", "PORTFOLIO", "ENTERPRISE"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _identifier(value: Any, field_name: str) -> str:
    text = _text(value)
    if not text:
        raise ValueError(f"{field_name} is required")
    if any(character.isspace() for character in text):
        raise ValueError(f"{field_name} must not contain whitespace")
    return text


def normalize_plugin_capabilities(value: Any) -> list[dict[str, Any]]:
    """Normalize plugin capabilities into deterministic registry records.

    Accepted input forms are strings or objects. String capabilities are treated
    as enabled, read-only reporting capabilities.
    """
    if value in (None, ""):
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("capabilities must be a list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if isinstance(item, str):
            capability_id = _identifier(item, "capability_id")
            record = {
                "capability_id": capability_id,
                "display_name": capability_id.replace("_", " ").replace("-", " ").title(),
                "enabled": True,
                "read_only": True,
            }
        elif isinstance(item, Mapping):
            capability_id = _identifier(
                item.get("capability_id") or item.get("id") or item.get("name"),
                "capability_id",
            )
            record = {
                "capability_id": capability_id,
                "display_name": _text(item.get("display_name") or item.get("name") or capability_id),
                "enabled": bool(item.get("enabled", True)),
                "read_only": bool(item.get("read_only", True)),
            }
            description = _text(item.get("description"))
            if description:
                record["description"] = description
        else:
            raise ValueError("capabilities entries must be strings or objects")
        if capability_id in seen:
            raise ValueError(f"duplicate capability_id: {capability_id}")
        if record["read_only"] is not True:
            raise ValueError(f"capability {capability_id} must be read-only")
        seen.add(capability_id)
        normalized.append(record)
    normalized.sort(key=lambda item: item["capability_id"])
    return normalized


def normalize_dashboard_artifacts(value: Any) -> list[dict[str, Any]]:
    """Normalize plugin-published artifact declarations.

    Paths are retained as declarative host-readable locations. This function
    does not open, resolve, or execute anything at those paths.
    """
    if value in (None, ""):
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError("dashboard_artifacts must be a list")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("dashboard_artifacts entries must be objects")
        artifact_id = _identifier(
            item.get("artifact_id") or item.get("report_id") or item.get("id"),
            "artifact_id",
        )
        if artifact_id in seen:
            raise ValueError(f"duplicate artifact_id: {artifact_id}")
        artifact_type = _identifier(
            item.get("artifact_type") or item.get("type") or item.get("report_id") or artifact_id,
            "artifact_type",
        ).upper()
        path = _text(item.get("path") or item.get("report_path") or item.get("artifact_path"))
        if not path:
            raise ValueError(f"artifact path is required for {artifact_id}")
        if PurePath(path).name in {"", ".", ".."}:
            raise ValueError(f"artifact path is invalid for {artifact_id}")
        artifact_format = _text(item.get("format") or PurePath(path).suffix.lstrip(".") or "JSON").upper()
        if artifact_format == "MD":
            artifact_format = "MARKDOWN"
        if artifact_format not in SUPPORTED_ARTIFACT_FORMATS:
            raise ValueError(f"unsupported artifact format for {artifact_id}: {artifact_format}")
        scope = _text(item.get("scope") or "STRATEGY").upper()
        if scope not in SUPPORTED_ARTIFACT_SCOPES:
            raise ValueError(f"unsupported artifact scope for {artifact_id}: {scope}")
        record = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "path": path,
            "format": artifact_format,
            "scope": scope,
            "authoritative": bool(item.get("authoritative", True)),
            "required": bool(item.get("required", False)),
            "read_only": True,
        }
        schema_version = _text(item.get("schema_version"))
        if schema_version:
            record["schema_version"] = schema_version
        description = _text(item.get("description"))
        if description:
            record["description"] = description
        seen.add(artifact_id)
        normalized.append(record)
    normalized.sort(key=lambda item: item["artifact_id"])
    return normalized


def build_plugin_contract_metadata(registration: Mapping[str, Any]) -> dict[str, Any]:
    """Build the backward-compatible Registry v2 metadata block."""
    capabilities = normalize_plugin_capabilities(registration.get("capabilities", []))
    artifacts = normalize_dashboard_artifacts(
        registration.get("dashboard_artifacts")
        or registration.get("published_artifacts")
        or []
    )
    capability_ids = {item["capability_id"] for item in capabilities if item["enabled"]}
    undeclared_types = sorted({
        item["artifact_type"].lower()
        for item in artifacts
        if item["artifact_type"].lower() not in capability_ids
    })
    return {
        "plugin_contract_version": PLUGIN_CONTRACT_VERSION,
        "capabilities": capabilities,
        "dashboard_artifacts": artifacts,
        "capability_count": len(capabilities),
        "published_artifact_count": len(artifacts),
        "contract_warnings": [
            f"Artifact type has no matching enabled capability: {item}"
            for item in undeclared_types
        ],
    }
