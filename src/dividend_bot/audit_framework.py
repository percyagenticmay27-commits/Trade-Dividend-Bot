"""Shared audit framework with strict platform and strategy scope isolation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .platform_entities import AuditFinding, AuditRun, FindingStatus, new_identity
from .platform_foundation import IdentifierKind, JsonSerializer, PlatformSettings, PlatformValidationError

MODULE_NAME = "audit_framework"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Deterministic platform and strategy audit modeling, rendering, and release gates."


@dataclass(frozen=True)
class AuditCheckResult:
    check_name: str
    status: FindingStatus
    message: str

    def validate(self) -> None:
        AuditFinding(self.check_name, self.status, self.message).validate()


@dataclass(frozen=True)
class AuditModel:
    scope_type: str
    scope_id: str
    audit_type: str
    completed_at: datetime
    checks: tuple[AuditCheckResult, ...]
    strategy_id: str | None = None

    def validate(self) -> None:
        if not self.scope_type.strip() or not self.scope_id.strip():
            raise PlatformValidationError("audit scope must not be empty")
        if not self.audit_type or self.audit_type != self.audit_type.upper():
            raise PlatformValidationError("audit_type must be non-empty uppercase text")
        if self.completed_at.tzinfo is None:
            raise PlatformValidationError("completed_at must be timezone-aware")
        if not self.checks:
            raise PlatformValidationError("audit must contain at least one check")
        if self.scope_type.upper() == "STRATEGY":
            if not self.strategy_id or self.strategy_id != self.strategy_id.upper():
                raise PlatformValidationError("strategy audits require uppercase strategy_id")
        elif self.strategy_id is not None:
            raise PlatformValidationError("platform audits must not carry strategy_id")
        for check in self.checks:
            check.validate()


@dataclass(frozen=True)
class ReleaseGateResult:
    passed: bool
    failures: tuple[str, ...]
    warnings: tuple[str, ...]


class AuditRenderer:
    def __init__(self, settings: PlatformSettings | None = None) -> None:
        self._settings = settings or PlatformSettings()
        self._settings.validate()

    def output_directory(self, model: AuditModel) -> Path:
        model.validate()
        scope = model.strategy_id.lower() if model.strategy_id else "platform"
        return self._settings.results_root / scope / "audits" / model.audit_type.lower()

    def render_json(self, model: AuditModel) -> str:
        model.validate()
        return JsonSerializer.dumps(model)

    def render_markdown(self, model: AuditModel) -> str:
        model.validate()
        lines = [
            f"# {model.audit_type.replace('_', ' ').title()}",
            "",
            f"- Scope Type: {model.scope_type}",
            f"- Scope ID: {model.scope_id}",
            f"- Strategy: {model.strategy_id or 'PLATFORM'}",
            f"- Completed At: {JsonSerializer.to_primitive(model.completed_at)}",
            "",
            "## Findings",
            "",
        ]
        for check in model.checks:
            lines.append(f"- [{check.status.value}] {check.check_name}: {check.message}")
        return "\n".join(lines) + "\n"

    def build_audit_run(self, model: AuditModel) -> AuditRun:
        model.validate()
        run = AuditRun(
            identity=new_identity(IdentifierKind.AUDIT),
            scope_type=model.scope_type,
            scope_id=model.scope_id,
            strategy_id=model.strategy_id,
            findings=tuple(AuditFinding(c.check_name, c.status, c.message) for c in model.checks),
            completed_at=model.completed_at,
        )
        run.validate()
        return run


def evaluate_release_gate(models: Iterable[AuditModel]) -> ReleaseGateResult:
    failures: list[str] = []
    warnings: list[str] = []
    seen = False
    for model in models:
        seen = True
        model.validate()
        for check in model.checks:
            label = f"{model.audit_type}:{check.check_name}"
            if check.status is FindingStatus.FAIL:
                failures.append(label)
            elif check.status is FindingStatus.WARNING:
                warnings.append(label)
    if not seen:
        raise PlatformValidationError("at least one audit model is required")
    return ReleaseGateResult(not failures, tuple(failures), tuple(warnings))


def ensure_single_audit_scope(models: tuple[AuditModel, ...]) -> tuple[str, str | None]:
    if not models:
        raise PlatformValidationError("at least one audit model is required")
    scopes = {(m.scope_type.upper(), m.strategy_id) for m in models}
    if len(scopes) != 1:
        raise PlatformValidationError("platform and strategy audits must not be combined")
    return next(iter(scopes))
