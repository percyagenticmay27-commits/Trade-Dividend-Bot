"""Filesystem loader for canonical strategy manifests."""

from __future__ import annotations

import json
from pathlib import Path

from .manifest import StrategyManifest


class ManifestLoadError(ValueError):
    """Raised when a strategy manifest cannot be loaded safely."""


class StrategyManifestLoader:
    def load(self, path: str | Path) -> StrategyManifest:
        manifest_path = Path(path)
        if not manifest_path.exists():
            raise ManifestLoadError(f"manifest not found: {manifest_path}")
        if not manifest_path.is_file():
            raise ManifestLoadError(f"manifest path is not a file: {manifest_path}")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise ManifestLoadError(f"unable to read manifest {manifest_path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise ManifestLoadError("manifest root must be a JSON object")
        try:
            return StrategyManifest.from_dict(payload)
        except (TypeError, ValueError) as exc:
            raise ManifestLoadError(f"invalid manifest {manifest_path}: {exc}") from exc
