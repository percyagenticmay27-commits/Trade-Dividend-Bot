from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from src.dividend_bot.strategy_decision_event_publisher import (
    publish_strategy_decision_event,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Publish one validated paper-only strategy decision event"
    )
    parser.add_argument("event_json", help="Path to one strategy decision event JSON object")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--replace-existing", action="store_true")
    args = parser.parse_args(argv)

    try:
        event = json.loads(Path(args.event_json).read_text(encoding="utf-8"))
        summary = publish_strategy_decision_event(
            event,
            results_dir=args.results_dir,
            replace_existing=args.replace_existing,
        )
    except Exception as exc:
        print(f"Decision event publication failed: {exc}")
        return 1

    print(f"Publication status: {summary['publication_status']}")
    print(f"Strategy: {summary['strategy_id']}")
    print(f"Decision ID: {summary['decision_id']}")
    print(f"Decision count: {summary['decision_count']}")
    print(f"Source path: {summary['path']}")
    print("Safety: PAPER ONLY / NO BROKER EXECUTION / NO CAPITAL MOVEMENT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
