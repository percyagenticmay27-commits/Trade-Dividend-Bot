"""Host-to-Swing transport for validated manual strategy intake.

The Enterprise AI CIO host never writes Swing strategy storage directly. It
invokes the Swing-owned intake CLI through the Swing virtualenv, passing a JSON
submission over stdin and accepting only the CLI's JSON response.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Mapping

PAPER_TRADE_MODE = True
LIVE_TRADING_ENABLED = False
BROKER_EXECUTION_ENABLED = False
ORDER_PLACEMENT_ENABLED = False
CAPITAL_MOVEMENT_ENABLED = False

DEFAULT_SWING_ROOT = Path("/home/tradebot/Trade-Swing-Bot/main")
DEFAULT_SWING_PYTHON = DEFAULT_SWING_ROOT / ".venv/bin/python"
SWING_INTAKE_MODULE = "swing_trade_bot.manual_entry_strategy_intake_cli"


def submit_manual_strategy_to_swing(
    submission: Mapping[str, Any],
    *,
    swing_root: Path = DEFAULT_SWING_ROOT,
    swing_python: Path | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    """Submit one form payload to the Swing-owned validator/persistence layer."""
    root = swing_root.resolve(strict=False)
    python_path = (swing_python or (root / ".venv/bin/python")).resolve(strict=False)
    if not root.is_dir():
        raise RuntimeError(f"Swing repository root is unavailable: {root}")
    if not python_path.is_file():
        raise RuntimeError(f"Swing Python runtime is unavailable: {python_path}")

    completed = subprocess.run(
        [str(python_path), "-m", SWING_INTAKE_MODULE],
        input=json.dumps(dict(submission)),
        text=True,
        capture_output=True,
        cwd=root,
        timeout=timeout_seconds,
        check=False,
    )
    stdout = completed.stdout.strip()
    try:
        response = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("Swing intake returned invalid JSON") from exc
    if not isinstance(response, dict):
        raise RuntimeError("Swing intake returned a non-object response")
    if response.get("paper_trade_mode") is not True:
        raise RuntimeError("Swing intake response did not preserve paper-only mode")
    if completed.returncode != 0 or response.get("ok") is not True:
        message = str(response.get("error") or completed.stderr.strip() or "Swing intake rejected submission")
        raise ValueError(message)
    return response
