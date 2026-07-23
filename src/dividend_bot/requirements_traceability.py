"""Validate required architecture, governance, workflow, and strategy artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .platform_foundation import PlatformValidationError

MODULE_NAME = "requirements_traceability"
MODULE_VERSION = "1.0.0"
MODULE_DESCRIPTION = "Release-gate validation for approved platform and Dividend Strategy requirements."


@dataclass(frozen=True)
class TraceabilityCheck:
    name: str
    path: str
    required_text: tuple[str, ...] = ()


@dataclass(frozen=True)
class TraceabilityResult:
    name: str
    path: str
    passed: bool
    message: str


BLUEPRINT_CHECKS: tuple[TraceabilityCheck, ...] = tuple(
    TraceabilityCheck(
        name=f"BP-{number:03d}",
        path=f"docs/blueprints/BP-{number:03d}_{filename}.md",
        required_text=("Status:", "FROZEN"),
    )
    for number, filename in (
        (0, "Blueprint_Index"),
        (1, "AI_CIO_Constitution"),
        (2, "Business_Entity_Catalog"),
        (3, "Enterprise_Data_Dictionary"),
        (4, "Entity_Relationship_Specification"),
        (5, "Platform_Service_Catalog"),
        (6, "Module_Contract_Library"),
        (7, "Dependency_Aware_Build_Sequence"),
        (8, "Implementation_Blueprint"),
    )
)

ADR_CHECKS: tuple[TraceabilityCheck, ...] = (
    TraceabilityCheck("ADR-001", "docs/adr/ADR-001_PostgreSQL_Primary_Persistence.md"),
    TraceabilityCheck("ADR-002", "docs/adr/ADR-002_Dual_Identifier_Model.md"),
    TraceabilityCheck("ADR-003", "docs/adr/ADR-003_Naming_Convention.md"),
    TraceabilityCheck("ADR-004", "docs/adr/ADR-004_Master_Company_Intelligence_Profile.md"),
    TraceabilityCheck("ADR-005", "docs/adr/ADR-005_Strategy_Report_Isolation.md"),
    TraceabilityCheck("ADR-006", "docs/adr/ADR-006_Strategy_Isolation.md"),
)

CORE_MODULE_CHECKS: tuple[TraceabilityCheck, ...] = (
    TraceabilityCheck(
        "platform foundation",
        "src/dividend_bot/platform_foundation.py",
        ("paper_trade_mode", "live_trading_enabled", "broker_execution_enabled"),
    ),
    TraceabilityCheck(
        "canonical entities",
        "src/dividend_bot/platform_entities.py",
        ("MasterCompanyIntelligenceProfile", "AICIODecision", "StrategyEvaluation"),
    ),
    TraceabilityCheck(
        "platform governance",
        "src/dividend_bot/platform_governance.py",
        ("EvidenceRepository", "InvestorOverride", "DecisionLedger"),
    ),
    TraceabilityCheck(
        "strategy framework",
        "src/dividend_bot/strategy_framework.py",
        ("StrategyRegistry", "paper_trade_mode"),
    ),
    TraceabilityCheck(
        "reporting framework",
        "src/dividend_bot/reporting_framework.py",
        ("StrategyReportModel", "ensure_single_strategy"),
    ),
    TraceabilityCheck(
        "audit framework",
        "src/dividend_bot/audit_framework.py",
        ("StrategyAuditModel", "ReleaseGate"),
    ),
    TraceabilityCheck(
        "Dividend Strategy adapter",
        "src/dividend_bot/dividend_strategy_adapter.py",
        ("DIVIDEND", "WEEKLY", "MONTHLY"),
    ),
    TraceabilityCheck(
        "requirements traceability matrix",
        "docs/architecture/PLATFORM_REQUIREMENTS_TRACEABILITY_MATRIX.md",
        ("Governance", "UI Template", "Workflow Design", "Deployment Gate"),
    ),
)


def validate_traceability(
    repository_root: Path | str = Path("."),
    checks: Iterable[TraceabilityCheck] | None = None,
) -> tuple[TraceabilityResult, ...]:
    """Validate required files and marker text without executing production logic."""
    root = Path(repository_root)
    selected = tuple(checks or (BLUEPRINT_CHECKS + ADR_CHECKS + CORE_MODULE_CHECKS))
    results: list[TraceabilityResult] = []

    for check in selected:
        target = root / check.path
        if not target.is_file():
            results.append(TraceabilityResult(check.name, check.path, False, "required file is missing"))
            continue

        text = target.read_text(encoding="utf-8")
        missing_markers = tuple(marker for marker in check.required_text if marker not in text)
        if missing_markers:
            results.append(
                TraceabilityResult(
                    check.name,
                    check.path,
                    False,
                    f"missing required markers: {', '.join(missing_markers)}",
                )
            )
            continue

        results.append(TraceabilityResult(check.name, check.path, True, "present and traceable"))

    return tuple(results)


def require_traceability(repository_root: Path | str = Path(".")) -> tuple[TraceabilityResult, ...]:
    """Raise when any approved release-gate artifact is missing or incomplete."""
    results = validate_traceability(repository_root)
    failures = tuple(result for result in results if not result.passed)
    if failures:
        summary = "; ".join(f"{item.name}: {item.message}" for item in failures)
        raise PlatformValidationError(f"requirements traceability failed: {summary}")
    return results


def build_traceability_summary(results: Iterable[TraceabilityResult]) -> dict[str, object]:
    resolved = tuple(results)
    passed = sum(1 for result in resolved if result.passed)
    failed = len(resolved) - passed
    return {
        "status": "PASS" if failed == 0 else "FAIL",
        "total_checks": len(resolved),
        "passed_checks": passed,
        "failed_checks": failed,
        "failures": [
            {"name": result.name, "path": result.path, "message": result.message}
            for result in resolved
            if not result.passed
        ],
    }
