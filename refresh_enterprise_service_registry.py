"""Refresh the AI CIO Enterprise service registry before allocation startup."""
from __future__ import annotations

import argparse
from pathlib import Path

from src.dividend_bot.enterprise_dividend_service_registry_event_wiring import (
    build_and_write_service_registry,
)

DEFAULT_CONFIG = Path("configs/external_strategy_registrations.json")
DEFAULT_OUTPUT_DIR = Path("results")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh the paper-only AI CIO service registry.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    try:
        registry = build_and_write_service_registry(
            args.output_dir,
            external_registration_config=args.config,
        )
    except Exception as exc:
        print(f"Enterprise registry refresh failed: {exc}")
        return 1
    summary = registry.get("summary", {})
    output_files = registry.get("output_files", {})
    print(f"Registry path: {output_files.get('json', '')}")
    print(f"Registry contract version: {registry.get('registry_contract_version', '1.0')}")
    print(f"Registered strategy count: {summary.get('strategy_plugin_count', 0)}")
    print(f"Accepted external strategy count: {summary.get('accepted_external_strategy_count', 0)}")
    print(f"Discovered capability count: {summary.get('capability_count', 0)}")
    print(f"Published artifact declaration count: {summary.get('published_artifact_count', 0)}")
    print(f"Strategies declaring capabilities: {summary.get('strategy_with_capabilities_count', 0)}")
    print(f"Strategies declaring artifacts: {summary.get('strategy_with_artifacts_count', 0)}")
    warnings = registry.get("external_registration_warnings", [])
    contract_warnings = registry.get("strategy_contracts", {}).get("contract_warnings", [])
    if warnings or contract_warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning.get('code')}: {warning.get('message')}")
        for warning in contract_warnings:
            print(f"- REGISTRY_V2_CONTRACT [{warning.get('strategy_id')}]: {warning.get('message')}")
    else:
        print("Warnings: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
