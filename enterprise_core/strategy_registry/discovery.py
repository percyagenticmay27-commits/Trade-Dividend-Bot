"""Filesystem discovery for Version 1 strategy plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .loader import ManifestLoadError, StrategyManifestLoader
from .manifest import StrategyManifest
from .registry import DuplicateStrategyError, StrategyRegistry
from .validator import StrategyManifestValidator


@dataclass(frozen=True)
class DiscoveryResult:
    discovered: tuple[StrategyManifest, ...]
    rejected: tuple[str, ...]
    warnings: tuple[str, ...]


class StrategyDiscoveryService:
    """Discover strategies by manifest contract without importing private code."""

    def __init__(
        self,
        loader: StrategyManifestLoader | None = None,
        validator: StrategyManifestValidator | None = None,
    ) -> None:
        self._loader = loader or StrategyManifestLoader()
        self._validator = validator or StrategyManifestValidator()

    def discover(
        self,
        roots: list[str | Path] | tuple[str | Path, ...],
        registry: StrategyRegistry | None = None,
    ) -> DiscoveryResult:
        target_registry = registry or StrategyRegistry()
        rejected: list[str] = []
        warnings: list[str] = []

        manifest_paths: list[Path] = []
        for root_value in roots:
            root = Path(root_value)
            if not root.exists():
                warnings.append(f"discovery root not found: {root}")
                continue
            if root.is_file() and root.name == "manifest.json":
                manifest_paths.append(root)
            elif root.is_dir():
                manifest_paths.extend(root.rglob("manifest.json"))

        for path in sorted(set(manifest_paths)):
            try:
                manifest = self._loader.load(path)
                validation = self._validator.validate(manifest, strategy_root=path.parent)
                warnings.extend(f"{path}: {message}" for message in validation.warnings)
                if not validation.valid:
                    rejected.append(f"{path}: {'; '.join(validation.errors)}")
                    continue
                target_registry.register(manifest)
            except (ManifestLoadError, DuplicateStrategyError) as exc:
                rejected.append(f"{path}: {exc}")

        return DiscoveryResult(target_registry.list(), tuple(rejected), tuple(warnings))
