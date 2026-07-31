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
    print(f"Registered strategy count: {summary.get('strategy_plugin_count', 0)}")
    print(f"Accepted external strategy count: {summary.get('accepted_external_strategy_count', 0)}")
    warnings = registry.get("external_registration_warnings", [])
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning.get('code')}: {warning.get('message')}")
    else:
        print("Warnings: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
