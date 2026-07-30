"""Version 1 Enterprise compatibility adapter for the existing Dividend Bot.

The adapter wraps the existing paper-cycle callable. It does not alter strategy
calculations, place orders, manage accounts, or import broker execution code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from enterprise_core.plugin_sdk.models import PluginContext, PluginRunResult
from enterprise_core.plugin_sdk.plugin import EnterpriseStrategyPlugin

DIVIDEND_STRATEGY_ID = "BOT-001"
DIVIDEND_STRATEGY_NAME = "Agentic-Robin-Dividend.bot"

CycleRunner = Callable[[PluginContext], Mapping[str, Any] | None]


@dataclass(frozen=True)
class DividendContractPaths:
    manifest: str = "enterprise_contracts/manifest.json"
    status: str = "enterprise_contracts/status.json"
    health: str = "enterprise_contracts/health.json"
    outputs: str = "enterprise_contracts/outputs.json"

    def to_dict(self) -> dict[str, str]:
        return {
            "manifest": self.manifest,
            "status": self.status,
            "health": self.health,
            "outputs": self.outputs,
        }


class DividendBotEnterprisePlugin(EnterpriseStrategyPlugin):
    """Expose the existing Dividend Bot through the Enterprise Plugin SDK."""

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(
        self,
        cycle_runner: CycleRunner,
        *,
        contract_paths: DividendContractPaths | None = None,
    ) -> None:
        if not callable(cycle_runner):
            raise TypeError("cycle_runner must be callable")
        self._cycle_runner = cycle_runner
        self._contract_paths = contract_paths or DividendContractPaths()
        self._context: PluginContext | None = None

    @property
    def strategy_id(self) -> str:
        return DIVIDEND_STRATEGY_ID

    def initialize(self, context: PluginContext) -> None:
        context.validate()
        if context.strategy_id != self.strategy_id:
            raise ValueError("PluginContext strategy_id does not match Dividend Bot")
        self._context = context
        self._write_manifest()
        self._write_contract(
            "status",
            {
                "strategy_id": self.strategy_id,
                "runtime_status": "INITIALIZED",
                "last_run_at": None,
            },
        )
        self._write_contract(
            "health",
            {
                "strategy_id": self.strategy_id,
                "health_status": "OK",
                "warnings": [],
            },
        )
        self._write_contract(
            "outputs",
            {
                "strategy_id": self.strategy_id,
                "output_files": [],
                "report_files": [],
                "data_files": [],
                "log_files": [],
            },
        )

    def run(self) -> PluginRunResult:
        context = self._require_context()
        try:
            payload = dict(self._cycle_runner(context) or {})
            status = str(payload.get("status") or "SUCCESS").upper()
            if status not in PluginRunResult.ALLOWED_STATUSES:
                status = "WARNING"
            output_paths = {
                str(name): str(path)
                for name, path in dict(payload.get("output_paths") or {}).items()
            }
            warnings = tuple(str(item) for item in payload.get("warnings") or ())
            metadata = dict(payload.get("metadata") or {})
            self._write_contract(
                "status",
                {
                    "strategy_id": self.strategy_id,
                    "runtime_status": "ONLINE" if status in {"SUCCESS", "WARNING"} else "ERROR",
                    "last_run_at": _utc_now(),
                    "last_run_status": status,
                },
            )
            self._write_contract(
                "health",
                {
                    "strategy_id": self.strategy_id,
                    "health_status": "OK" if status == "SUCCESS" else status,
                    "warnings": list(warnings),
                },
            )
            self._write_contract(
                "outputs",
                {
                    "strategy_id": self.strategy_id,
                    "output_files": sorted(set(output_paths.values())),
                    "outputs": output_paths,
                },
            )
            result = PluginRunResult(
                strategy_id=self.strategy_id,
                status=status,
                output_paths=output_paths,
                warnings=warnings,
                metadata=metadata,
            )
            result.validate()
            return result
        except Exception as exc:
            self._write_contract(
                "status",
                {
                    "strategy_id": self.strategy_id,
                    "runtime_status": "ERROR",
                    "last_run_at": _utc_now(),
                    "last_run_status": "FAILED",
                },
            )
            self._write_contract(
                "health",
                {
                    "strategy_id": self.strategy_id,
                    "health_status": "ERROR",
                    "warnings": [str(exc)],
                },
            )
            raise

    def shutdown(self) -> None:
        if self._context is not None:
            self._write_contract(
                "status",
                {
                    "strategy_id": self.strategy_id,
                    "runtime_status": "OFFLINE",
                    "last_run_at": _utc_now(),
                },
            )

    def _write_manifest(self) -> None:
        self._write_contract(
            "manifest",
            {
                "strategy_id": self.strategy_id,
                "strategy_name": DIVIDEND_STRATEGY_NAME,
                "version": "1.0.0",
                "lifecycle_status": "PRODUCTION_PAPER",
                "certification_level": "PRODUCTION_PAPER",
                "entrypoint": "run_daily_paper_cycle.py",
                "capabilities": ["dividend_income", "portfolio_reporting", "paper_portfolio_management"],
                "permissions": ["market_data.read", "reports.write", "email.send"],
                "required_services": ["enterprise_market_data"],
                "output_paths": self._contract_paths.to_dict(),
                "state_owner": self.strategy_id,
                "paper_trade_mode": True,
                "live_trading_enabled": False,
                "broker_execution_enabled": False,
                "schema_version": "1.0",
            },
        )

    def _write_contract(self, name: str, payload: Mapping[str, Any]) -> Path:
        context = self._require_context()
        relative = self._contract_paths.to_dict()[name]
        root = Path(context.strategy_root).resolve()
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"contract path escapes strategy root: {name}") from exc
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(payload), indent=2, sort_keys=True), encoding="utf-8")
        return target

    def _require_context(self) -> PluginContext:
        if self._context is None:
            raise RuntimeError("Dividend Bot plugin is not initialized")
        return self._context


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
