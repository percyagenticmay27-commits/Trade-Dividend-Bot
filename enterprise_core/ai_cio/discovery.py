"""AI CIO contract-only strategy discovery and inventory snapshots."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from enterprise_core.strategy_registry.health_monitor import StrategyHealthMonitor
from enterprise_core.strategy_registry.loader import ManifestLoadError, StrategyManifestLoader
from enterprise_core.strategy_registry.registry import DuplicateStrategyError, StrategyRegistry
from enterprise_core.strategy_registry.validator import StrategyManifestValidator


@dataclass(frozen=True)
class StrategyDiscoveryRecord:
    strategy_id: str
    strategy_name: str
    version: str
    lifecycle_status: str
    certification_level: str
    capabilities: tuple[str, ...]
    required_services: tuple[str, ...]
    health_status: str
    health_score: int
    strategy_root: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AICIODiscoverySnapshot:
    strategies: tuple[StrategyDiscoveryRecord, ...]
    rejected: tuple[str, ...]
    warnings: tuple[str, ...]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    schema_version: str = "1.0"
    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False

    @property
    def strategy_count(self) -> int:
        return len(self.strategies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "strategy_count": self.strategy_count,
            "strategies": [record.to_dict() for record in self.strategies],
            "rejected": list(self.rejected),
            "warnings": list(self.warnings),
            "paper_trade_mode": self.paper_trade_mode,
            "live_trading_enabled": self.live_trading_enabled,
            "broker_execution_enabled": self.broker_execution_enabled,
        }


class AICIODiscoveryService:
    """Build an AI CIO inventory from public strategy contracts only."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(
        self,
        loader: StrategyManifestLoader | None = None,
        validator: StrategyManifestValidator | None = None,
        health_monitor: StrategyHealthMonitor | None = None,
    ) -> None:
        self._loader = loader or StrategyManifestLoader()
        self._validator = validator or StrategyManifestValidator()
        self._health_monitor = health_monitor or StrategyHealthMonitor()

    def discover(self, roots: Iterable[str | Path]) -> AICIODiscoverySnapshot:
        registry = StrategyRegistry()
        records: list[StrategyDiscoveryRecord] = []
        rejected: list[str] = []
        warnings: list[str] = []

        for path in self._manifest_paths(roots, warnings):
            try:
                manifest = self._loader.load(path)
                validation = self._validator.validate(manifest, strategy_root=path.parent)
                warnings.extend(f"{path}: {item}" for item in validation.warnings)
                if not validation.valid:
                    rejected.append(f"{path}: {'; '.join(validation.errors)}")
                    continue
                registry.register(manifest)
                health = self._health_monitor.assess(manifest, path.parent)
                records.append(
                    StrategyDiscoveryRecord(
                        strategy_id=manifest.strategy_id,
                        strategy_name=manifest.strategy_name,
                        version=manifest.version,
                        lifecycle_status=manifest.lifecycle_status,
                        certification_level=manifest.certification_level,
                        capabilities=tuple(manifest.capabilities),
                        required_services=tuple(manifest.required_services),
                        health_status=health.status,
                        health_score=health.score,
                        strategy_root=str(path.parent.resolve()),
                        warnings=tuple(health.warnings),
                    )
                )
            except (ManifestLoadError, DuplicateStrategyError, ValueError) as exc:
                rejected.append(f"{path}: {exc}")

        records.sort(key=lambda record: record.strategy_id)
        return AICIODiscoverySnapshot(tuple(records), tuple(rejected), tuple(warnings))

    @staticmethod
    def write_snapshot(snapshot: AICIODiscoverySnapshot, path: str | Path) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(snapshot.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
        return target

    @staticmethod
    def _manifest_paths(roots: Iterable[str | Path], warnings: list[str]) -> tuple[Path, ...]:
        paths: set[Path] = set()
        for root_value in roots:
            root = Path(root_value)
            if not root.exists():
                warnings.append(f"discovery root not found: {root}")
                continue
            if root.is_file() and root.name == "manifest.json":
                paths.add(root)
            elif root.is_dir():
                paths.update(root.rglob("manifest.json"))
        return tuple(sorted(paths))
