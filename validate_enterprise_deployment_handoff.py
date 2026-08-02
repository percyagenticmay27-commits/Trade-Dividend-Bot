"""Report the Phase 7.5 local-to-DigitalOcean validation handoff."""
from __future__ import annotations

import argparse
from typing import Sequence

from src.dividend_bot.enterprise_deployment_handoff import (
    build_and_write_deployment_handoff,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect paper-only local and DigitalOcean validation readiness"
    )
    parser.add_argument("--root-dir", default=".")
    parser.add_argument("--results-dir", default="results")
    args = parser.parse_args(argv)
    report = build_and_write_deployment_handoff(
        root_dir=args.root_dir, results_dir=args.results_dir
    )
    print(f"Environment: {report['environment']}")
    print(f"Handoff status: {report['handoff_status']}")
    print(f"Local validation ready: {report['local_validation_ready']}")
    print(f"Production validation ready: {report['production_validation_ready']}")
    for item in report["next_actions"]:
        print(f"NEXT: {item}")
    for item in report["blockers"]:
        print(f"BLOCKER: {item}")
    return 0 if report["handoff_status"] in {"LOCAL_READY", "READY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
