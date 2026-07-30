"""Enterprise compatibility validation for strategy manifests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import StrategyManifest


@dataclass(frozen=True)
class ManifestValidationResult:
    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


class StrategyManifestValidator:
    SUPPORTED_SCHEMA_VERSIONS = frozenset({"1.0"})
    ALLOWED_LIFECYCLE_STATUSES = frozenset(
        {"DEVELOPMENT", "QA", "PAPER_CERTIFIED", "PRODUCTION_PAPER", "RETIRED"}
    )
    ALLOWED_CERTIFICATION_LEVELS = frozenset(
        {"UNCERTIFIED", "DEVELOPMENT", "QA", "PAPER_CERTIFIED", "PRODUCTION_PAPER"}
    )
    FORBIDDEN_PERMISSIONS = frozenset(
        {"broker_execution", "live_trading", "capital_transfer", "account_management"}
    )

    def validate(
        self,
        manifest: StrategyManifest,
        *,
        strategy_root: str | Path | None = None,
    ) -> ManifestValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        try:
            manifest.validate()
        except ValueError as exc:
            errors.append(str(exc))

        if manifest.schema_version not in self.SUPPORTED_SCHEMA_VERSIONS:
            errors.append(f"unsupported schema_version: {manifest.schema_version}")
        if manifest.lifecycle_status not in self.ALLOWED_LIFECYCLE_STATUSES:
            errors.append(f"unsupported lifecycle_status: {manifest.lifecycle_status}")
        if manifest.certification_level not in self.ALLOWED_CERTIFICATION_LEVELS:
            errors.append(f"unsupported certification_level: {manifest.certification_level}")

        forbidden = self.FORBIDDEN_PERMISSIONS.intersection(
            permission.lower() for permission in manifest.permissions
        )
        if forbidden:
            errors.append(f"forbidden permissions requested: {', '.join(sorted(forbidden))}")

        if "enterprise_market_data" not in {
            service.lower() for service in manifest.required_services
        }:
            warnings.append("strategy does not declare enterprise_market_data service")

        if strategy_root is not None:
            root = Path(strategy_root).resolve()
            entrypoint = (root / manifest.entrypoint).resolve()
            try:
                entrypoint.relative_to(root)
            except ValueError:
                errors.append("entrypoint escapes strategy root")
            else:
                if not entrypoint.exists():
                    errors.append(f"entrypoint not found: {manifest.entrypoint}")
            for output_name, output_path in manifest.output_paths.items():
                resolved = (root / output_path).resolve()
                try:
                    resolved.relative_to(root)
                except ValueError:
                    errors.append(f"output path escapes strategy root: {output_name}")

        return ManifestValidationResult(not errors, tuple(errors), tuple(warnings))
