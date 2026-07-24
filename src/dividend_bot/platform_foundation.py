"""Shared, strategy-neutral foundation services for the paper-only platform."""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import date, datetime, timezone
from enum import Enum
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any, Mapping
from uuid import UUID, uuid4

MODULE_NAME = "platform_foundation"
MODULE_VERSION = "1.0.1"
MODULE_DESCRIPTION = "Strategy-neutral configuration, identifiers, versions, and serialization."


class PlatformValidationError(ValueError):
    """Raised when a permanent platform rule is violated."""


@dataclass(frozen=True)
class PlatformSettings:
    """Immutable platform safety and path settings."""

    paper_trade_mode: bool = True
    live_trading_enabled: bool = False
    broker_execution_enabled: bool = False
    results_root: Path = Path("results")
    reports_root: Path = Path("reports")
    timezone_name: str = "UTC"

    def validate(self) -> None:
        """Enforce the permanent paper-only safety boundary."""
        if self.paper_trade_mode is not True:
            raise PlatformValidationError("paper_trade_mode must remain True")
        if self.live_trading_enabled is not False:
            raise PlatformValidationError("live_trading_enabled must remain False")
        if self.broker_execution_enabled is not False:
            raise PlatformValidationError("broker_execution_enabled must remain False")

    def strategy_results_path(self, strategy_id: str, report_type: str | None = None) -> Path:
        """Return a normalized, strategy-isolated output path."""
        strategy = _normalize_path_segment(strategy_id)
        path = self.results_root / strategy
        if report_type:
            path /= _normalize_path_segment(report_type)
        return path


class IdentifierKind(str, Enum):
    """Supported public identifier prefixes."""

    COMPANY = "COM"
    PROFILE = "MCIP"
    EVIDENCE = "EVR"
    DECISION = "DEC"
    STRATEGY = "STR"
    REPORT = "RPT"
    AUDIT = "AUD"
    LEARNING = "LRN"
    POSITION = "POS"


class IdentifierFactory:
    """Create UUID internal identifiers and human-readable external identifiers."""

    _lock = Lock()
    _counters: dict[tuple[str, int], int] = {}

    @staticmethod
    def new_internal_id() -> UUID:
        """Create a globally unique internal identifier."""
        return uuid4()

    @classmethod
    def new_public_id(
        cls,
        kind: IdentifierKind | str,
        *,
        year: int | None = None,
        sequence: int | None = None,
    ) -> str:
        """Create an identifier such as ``DEC-2026-000001``.

        Explicit sequences are useful for persistence-backed callers. When omitted,
        an in-process monotonic sequence is used for deterministic formatting only.
        """
        prefix = kind.value if isinstance(kind, IdentifierKind) else str(kind).upper()
        if not re.fullmatch(r"[A-Z][A-Z0-9]{1,7}", prefix):
            raise PlatformValidationError(f"invalid identifier prefix: {prefix!r}")
        resolved_year = year or datetime.now(timezone.utc).year
        if resolved_year < 2000 or resolved_year > 9999:
            raise PlatformValidationError("year must be between 2000 and 9999")
        if sequence is None:
            with cls._lock:
                key = (prefix, resolved_year)
                cls._counters[key] = cls._counters.get(key, 0) + 1
                sequence = cls._counters[key]
        if sequence < 1 or sequence > 999999:
            raise PlatformValidationError("sequence must be between 1 and 999999")
        return f"{prefix}-{resolved_year:04d}-{sequence:06d}"


@dataclass(frozen=True)
class ModuleVersion:
    """Registered module version metadata."""

    module_name: str
    module_version: str
    description: str = ""

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.module_name):
            raise PlatformValidationError("module_name must use snake_case")
        if not re.fullmatch(r"\d+\.\d+\.\d+", self.module_version):
            raise PlatformValidationError("module_version must use semantic versioning")


class VersionRegistry:
    """In-memory registry used to detect duplicate or conflicting module versions."""

    def __init__(self) -> None:
        self._versions: dict[str, ModuleVersion] = {}

    def register(self, version: ModuleVersion) -> None:
        version.validate()
        existing = self._versions.get(version.module_name)
        if existing and existing != version:
            raise PlatformValidationError(
                f"conflicting registration for {version.module_name}: "
                f"{existing.module_version} != {version.module_version}"
            )
        self._versions[version.module_name] = version

    def get(self, module_name: str) -> ModuleVersion:
        try:
            return self._versions[module_name]
        except KeyError as exc:
            raise PlatformValidationError(f"module is not registered: {module_name}") from exc

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {name: asdict(value) for name, value in sorted(self._versions.items())}


class JsonSerializer:
    """Deterministic JSON serialization for platform records and reports."""

    @classmethod
    def dumps(cls, value: Any, *, indent: int = 2) -> str:
        return json.dumps(
            cls.to_primitive(value),
            indent=indent,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ) + "\n"

    @classmethod
    def to_primitive(cls, value: Any) -> Any:
        if is_dataclass(value):
            return cls.to_primitive(asdict(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, Path):
            return value.as_posix()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise PlatformValidationError("datetime values must be timezone-aware")
            return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, Mapping):
            return {str(key): cls.to_primitive(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.to_primitive(item) for item in value]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        raise TypeError(f"unsupported serialization type: {type(value).__name__}")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def _normalize_path_segment(value: str) -> str:
    normalized = value.strip().lower().replace(" ", "_").replace("-", "_")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_]*", normalized):
        raise PlatformValidationError(f"invalid path segment: {value!r}")
    return normalized


DEFAULT_PLATFORM_SETTINGS = PlatformSettings()
DEFAULT_PLATFORM_SETTINGS.validate()
