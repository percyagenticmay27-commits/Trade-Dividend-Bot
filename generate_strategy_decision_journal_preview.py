from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from src.dividend_bot.strategy_decision_journal_renderer import (
    render_strategy_decision_journal_document,
)


def _read_json(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Decision Journal input must be a JSON object")
    return payload


def generate_preview(input_path: Path, output_path: Path) -> Path:
    journal = _read_json(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_strategy_decision_journal_document(journal),
        encoding="utf-8",
    )
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a read-only strategy Decision Journal HTML preview."
    )
    parser.add_argument("input", type=Path, help="Strategy Decision Journal JSON path")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("results/strategy-decision-journal-preview.html"),
    )
    args = parser.parse_args()
    generated = generate_preview(args.input, args.output)
    print(f"Decision Journal preview: {generated}")
    print("Safety: PAPER ONLY / READ ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
