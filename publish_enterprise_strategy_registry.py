"""Publish the canonical Phase 7.6 Enterprise strategy registry."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_strategy_registry_publisher import (
    publish_enterprise_strategy_registry,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish canonical paper-only Enterprise strategy registrations"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument(
        "--source", default="config/enterprise_strategy_registry.json"
    )
    parser.add_argument(
        "--target", default="results/enterprise_dividend_service_registry.json"
    )
    args = parser.parse_args(argv)
    report = publish_enterprise_strategy_registry(
        root_dir=args.root_dir,
        source_path=args.source,
        target_path=args.target,
    )
    print(f"Registry publish status: {report['publish_status']}")
    print(f"Strategies: {', '.join(report['strategy_ids']) or 'none'}")
    print(f"Target: {report['target_path']}")
    for error in report["errors"]:
        print(f"ERROR: {error}")
    return 0 if report["publish_status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
