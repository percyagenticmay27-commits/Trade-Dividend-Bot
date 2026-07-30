"""Contract-based strategy health monitoring without importing strategy code."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .manifest import StrategyManifest


@dataclass(frozen=True)
class HealthAssessment:
    strategy_id: str
    status: str
    score: int
    missing_files: tuple[str, ...]
    warnings: tuple[str, ...]
    checked_at: str


class StrategyHealthMonitor:
    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def assess(self, manifest: StrategyManifest, strategy_root: str | Path) -> HealthAssessment:
        manifest.validate()
        root = Path(strategy_root)
        missing: list[str] = []
        warnings: list[str] = []
        score = 100

        for contract_name in ("status", "health", "outputs"):
            relative_path = manifest.output_paths[contract_name]
            path = root / relative_path
            if not path.exists():
                missing.append(relative_path)
                score -= 25
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                warnings.append(f"invalid {contract_name} contract: {exc}")
                score -= 20
                continue
            if not isinstance(payload, dict):
                warnings.append(f"{contract_name} contract root must be an object")
                score -= 20
                continue
            self._inspect_contract(contract_name, payload, warnings)

        score = max(0, min(100, score))
        if score >= 90 and not warnings:
            status = "HEALTHY"
        elif score >= 65:
            status = "WARNING"
        else:
            status = "ERROR"
        return HealthAssessment(
            strategy_id=manifest.strategy_id,
            status=status,
            score=score,
            missing_files=tuple(missing),
            warnings=tuple(warnings),
            checked_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def _inspect_contract(name: str, payload: dict[str, Any], warnings: list[str]) -> None:
        strategy_id = payload.get("strategy_id") or payload.get("bot_id")
        if not strategy_id:
            warnings.append(f"{name} contract does not identify its strategy")
        if name == "status" and not (payload.get("runtime_status") or payload.get("status")):
            warnings.append("status contract does not declare runtime status")
        if name == "health" and not (payload.get("health_status") or payload.get("status")):
            warnings.append("health contract does not declare health status")
        if name == "outputs" and not any(
            key in payload for key in ("output_files", "report_files", "data_files", "outputs")
        ):
            warnings.append("outputs contract does not declare output files")
