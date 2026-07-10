"""Static Version 1.0 release auditor for the paper-only Dividend Bot.

The auditor inventories Python modules and tests, verifies the required 17-stage
architecture, compiles source text with Python's built-in compiler, scans the AST
for forbidden execution/network behavior, detects real test references, and
writes JSON/Markdown reports. It never invokes brokers, shell commands,
subprocesses, or external networks.
"""
from __future__ import annotations

import ast
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Set

MODULE_NAME = "version_1_0_release_audit"
MODULE_VERSION = "1.1.0"
SCHEMA_VERSION = "1.0"
PAPER_TRADE_MODE = True
REPORTING_ONLY = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False

REQUIRED_STAGE_MODULES = [
    "market_regime_engine.py", "market_intelligence_engine.py",
    "momentum_score_engine.py", "entry_score_engine.py", "conviction_engine.py",
    "dividend_ranking_engine.py", "opportunity_pairing_engine.py",
    "portfolio_decision_engine.py", "capital_allocation_engine.py",
    "portfolio_construction_engine.py", "portfolio_rebalance_engine.py",
    "income_reinvestment_engine.py", "portfolio_lifecycle_engine.py",
    "daily_portfolio_command_center.py", "weekly_portfolio_review_engine.py",
    "strategy_performance_analytics_engine.py", "monthly_portfolio_review_engine.py",
]

REQUIRED_CONTROL_FILES = [
    "stage_input_adapters.py", "master_portfolio_orchestrator.py",
    "run_daily_dividend_cycle.py",
]

EXCLUDED_PARTS = {".git", ".venv", "venv", "env", "__pycache__", ".pytest_cache", "site-packages"}
FORBIDDEN_IMPORT_ROOTS = {"subprocess", "requests", "socket", "robinhood", "robin_stocks"}
FORBIDDEN_IMPORT_NAMES = {"urllib.request", "http.client"}
FORBIDDEN_CALL_NAMES = {
    "os.system", "subprocess.run", "subprocess.call", "subprocess.Popen",
    "place_order", "submit_order", "execute_order", "execute_trade",
}


@dataclass(frozen=True)
class ReleaseAuditReport:
    module_name: str
    module_version: str
    schema_version: str
    generated_at_utc: str
    paper_trade_mode: bool
    reporting_only: bool
    live_trading_enabled: bool
    broker_execution_enabled: bool
    audit_status: str
    python_file_count: int
    production_module_count: int
    test_file_count: int
    required_stage_count: int
    present_required_stage_count: int
    detected_tested_module_count: int
    missing_required_stage_modules: List[str]
    missing_control_files: List[str]
    compile_errors: List[Dict[str, str]]
    safety_findings: List[Dict[str, Any]]
    production_modules_without_matching_tests: List[str]
    warnings: List[str]
    errors: List[str]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_excluded(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def discover_python_files(root_path: str = ".") -> List[Path]:
    root = Path(root_path)
    return sorted(path for path in root.rglob("*.py") if not _is_excluded(path.relative_to(root)))


def compile_source_files(paths: Iterable[Path], root_path: str = ".") -> List[Dict[str, str]]:
    root = Path(root_path)
    errors: List[Dict[str, str]] = []
    for path in paths:
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append({"path": str(path.relative_to(root)), "error": str(exc)})
    return errors


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def scan_safety(paths: Iterable[Path], root_path: str = ".") -> List[Dict[str, Any]]:
    root = Path(root_path)
    findings: List[Dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(root)
        if relative.name.startswith("test_") or relative.name == Path(__file__).name:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root_name = alias.name.split(".", 1)[0]
                    if root_name in FORBIDDEN_IMPORT_ROOTS or alias.name in FORBIDDEN_IMPORT_NAMES:
                        findings.append({"path": str(relative), "line": node.lineno, "kind": "import", "name": alias.name})
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                root_name = module.split(".", 1)[0]
                if root_name in FORBIDDEN_IMPORT_ROOTS or module in FORBIDDEN_IMPORT_NAMES:
                    findings.append({"path": str(relative), "line": node.lineno, "kind": "import", "name": module})
            elif isinstance(node, ast.Call):
                name = _dotted_name(node.func)
                if name in FORBIDDEN_CALL_NAMES or name.split(".")[-1] in FORBIDDEN_CALL_NAMES:
                    findings.append({"path": str(relative), "line": node.lineno, "kind": "call", "name": name})
    return findings


def matching_test_name(module_path: Path) -> str:
    return f"test_{module_path.stem}.py"


def discover_tested_module_stems(test_paths: Iterable[Path]) -> Set[str]:
    """Detect modules referenced by tests through imports or explicit source use."""
    referenced: Set[str] = set()
    for path in test_paths:
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    referenced.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                referenced.add(node.module.split(".", 1)[0])
        # Some legacy tests inspect module files by path without importing them.
        for token in source.replace("\\", "/").split():
            cleaned = token.strip("'\"`()[]{}:,;")
            if cleaned.endswith(".py"):
                referenced.add(Path(cleaned).stem)
    return referenced


def module_has_detected_test(module_path: Path, test_paths: Iterable[Path], referenced_stems: Set[str]) -> bool:
    expected = matching_test_name(module_path)
    if any(path.name == expected for path in test_paths):
        return True
    return module_path.stem in referenced_stems


def build_version_1_0_release_audit(root_path: str = ".") -> Dict[str, Any]:
    root = Path(root_path)
    python_files = discover_python_files(root_path)
    basenames = {path.name for path in python_files}
    tests = [path for path in python_files if path.name.startswith("test_")]
    production = [path for path in python_files if not path.name.startswith("test_")]

    missing_stages = [name for name in REQUIRED_STAGE_MODULES if name not in basenames]
    missing_controls = [name for name in REQUIRED_CONTROL_FILES if name not in basenames]
    compile_errors = compile_source_files(python_files, root_path)
    safety_findings = scan_safety(production, root_path)
    referenced_stems = discover_tested_module_stems(tests)

    no_test: List[str] = []
    tested_count = 0
    for path in production:
        if path.name in {"__init__.py", Path(__file__).name}:
            continue
        if module_has_detected_test(path, tests, referenced_stems):
            tested_count += 1
        else:
            no_test.append(str(path.relative_to(root)))

    warnings: List[str] = []
    errors: List[str] = []
    if no_test:
        warnings.append("One or more production modules have no detected pytest reference.")
    if missing_stages:
        errors.append("Required stage modules are missing.")
    if missing_controls:
        errors.append("Required orchestration/control files are missing.")
    if compile_errors:
        errors.append("One or more Python files failed built-in compilation.")
    if safety_findings:
        errors.append("Forbidden execution, broker, process, or network behavior was detected.")

    status = "FAIL" if errors else ("WARNING" if warnings else "PASS")
    report = asdict(ReleaseAuditReport(
        MODULE_NAME, MODULE_VERSION, SCHEMA_VERSION, _now(), True, True, False, False,
        status, len(python_files), len(production), len(tests), len(REQUIRED_STAGE_MODULES),
        len(REQUIRED_STAGE_MODULES) - len(missing_stages), tested_count, missing_stages,
        missing_controls, compile_errors, safety_findings, sorted(no_test), warnings, errors,
    ))
    validate_version_1_0_release_audit(report)
    return report


def validate_version_1_0_release_audit(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        raise ValueError("payload must be a mapping")
    required = set(ReleaseAuditReport.__dataclass_fields__)
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    for field, expected in {
        "paper_trade_mode": True, "reporting_only": True,
        "live_trading_enabled": False, "broker_execution_enabled": False,
    }.items():
        if payload[field] is not expected:
            raise ValueError(f"{field} must be {expected}")
    if payload["audit_status"] not in {"PASS", "WARNING", "FAIL"}:
        raise ValueError("unsupported audit_status")
    for field in [
        "python_file_count", "production_module_count", "test_file_count",
        "required_stage_count", "present_required_stage_count", "detected_tested_module_count",
    ]:
        if not isinstance(payload[field], int) or isinstance(payload[field], bool) or payload[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    for field in [
        "missing_required_stage_modules", "missing_control_files", "compile_errors",
        "safety_findings", "production_modules_without_matching_tests", "warnings", "errors",
    ]:
        if not isinstance(payload[field], list):
            raise ValueError(f"{field} must be a list")
    return True


def format_version_1_0_release_audit_markdown(payload: Mapping[str, Any]) -> str:
    validate_version_1_0_release_audit(payload)
    lines = [
        "# Dividend Bot Version 1.0 Release Audit", "",
        f"- Audit Status: {payload['audit_status']}",
        f"- Python Files: {payload['python_file_count']}",
        f"- Production Modules: {payload['production_module_count']}",
        f"- Test Files: {payload['test_file_count']}",
        f"- Detected Tested Modules: {payload['detected_tested_module_count']}",
        f"- Required Stages Present: {payload['present_required_stage_count']}/{payload['required_stage_count']}",
        "", "## Missing Required Stage Modules",
    ]
    lines.extend(f"- {item}" for item in payload["missing_required_stage_modules"]) or lines.append("- None")
    lines += ["", "## Missing Control Files"]
    lines.extend(f"- {item}" for item in payload["missing_control_files"]) or lines.append("- None")
    lines += ["", "## Compile Errors"]
    lines.extend(f"- {item['path']}: {item['error']}" for item in payload["compile_errors"]) or lines.append("- None")
    lines += ["", "## Safety Findings"]
    lines.extend(f"- {item['path']}:{item['line']} {item['kind']} {item['name']}" for item in payload["safety_findings"]) or lines.append("- None")
    lines += ["", "## Production Modules Without Detected Tests"]
    lines.extend(f"- {item}" for item in payload["production_modules_without_matching_tests"]) or lines.append("- None")
    lines += ["", "## Warnings"]
    lines.extend(f"- {item}" for item in payload["warnings"]) or lines.append("- None")
    lines += ["", "## Errors"]
    lines.extend(f"- {item}" for item in payload["errors"]) or lines.append("- None")
    return "\n".join(lines) + "\n"


def write_version_1_0_release_audit(
    root_path: str = ".",
    json_path: str = "version_1_0_release_audit.json",
    markdown_path: str = "version_1_0_release_audit.md",
) -> Dict[str, Any]:
    payload = build_version_1_0_release_audit(root_path)
    root = Path(root_path)
    (root / json_path).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (root / markdown_path).write_text(format_version_1_0_release_audit_markdown(payload), encoding="utf-8")
    return payload


if __name__ == "__main__":
    report = write_version_1_0_release_audit()
    print(f"Dividend Bot Version 1.0 Release Audit: {report['audit_status']}")
