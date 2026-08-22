"""Host-to-Swing transport for explicit user shadow strategy promotion."""
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
AUTO_PROMOTION_ENABLED = False

DEFAULT_SWING_ROOT = Path("/home/tradebot/Trade-Swing-Bot/main")
SWING_PROMOTION_MODULE = "swing_trade_bot.shadow_strategy_promotion_cli"


def promote_shadow_strategy_in_swing(
    submission: Mapping[str, Any],
    *,
    swing_root: Path = DEFAULT_SWING_ROOT,
    swing_python: Path | None = None,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    root = swing_root.resolve(strict=False)
    python_path = (swing_python or (root / ".venv/bin/python")).resolve(strict=False)
    if not root.is_dir():
        raise RuntimeError(f"Swing repository root is unavailable: {root}")
    if not python_path.is_file():
        raise RuntimeError(f"Swing Python runtime is unavailable: {python_path}")
    payload = {
        "underlying_symbol": str(submission.get("underlying_symbol") or "").strip().upper(),
        "strategy_id": str(submission.get("strategy_id") or "").strip().upper(),
        "user_confirmed": submission.get("user_confirmed") is True,
    }
    completed = subprocess.run(
        [str(python_path), "-m", SWING_PROMOTION_MODULE],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=root,
        timeout=timeout_seconds,
        check=False,
    )
    try:
        response = json.loads(completed.stdout.strip()) if completed.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise RuntimeError("Swing promotion returned invalid JSON") from exc
    if not isinstance(response, dict) or response.get("paper_trade_mode") is not True:
        raise RuntimeError("Swing promotion response did not preserve paper-only mode")
    if completed.returncode != 0 or response.get("ok") is not True:
        raise ValueError(str(response.get("error") or completed.stderr.strip() or "Swing rejected promotion"))
    return response
