#!/usr/bin/env python3
"""Root-owned read-only Codex/Robinhood MCP handoff.

This entry point is intended only for systemd ExecStartPre=+ execution. It uses
root's existing Codex OAuth profile, accepts market-data operations only, and
writes sanitized normalized JSON for the unprivileged tradebot runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import pwd
import grp
import tempfile
from pathlib import Path

from src.dividend_bot.codex_robinhood_market_data_bridge import run_codex_market_data

ALLOWED_OPERATIONS = {"get_quote", "get_history"}


def atomic_write_handoff(path: Path, payload: dict, owner: str = "tradebot", group: str = "tradebot") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, 0o640)
        os.chown(temporary_name, pwd.getpwnam(owner).pw_uid, grp.getgrnam(group).gr_gid)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--operation", choices=sorted(ALLOWED_OPERATIONS), required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--period", default="1mo")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--output-dir", default="/run/enterprise-market-data-handoff")
    parser.add_argument("--codex-path", default="/usr/local/bin/codex")
    parser.add_argument("--timeout-seconds", type=int, default=45)
    args = parser.parse_args()

    if os.geteuid() != 0:
        raise PermissionError("root-owned Codex handoff must run as root")

    payload = run_codex_market_data(
        args.operation,
        args.symbol,
        args.period if args.operation == "get_history" else "",
        args.interval if args.operation == "get_history" else "",
        timeout_seconds=args.timeout_seconds,
        codex_path=args.codex_path,
    )
    safe_symbol = args.symbol.strip().upper()
    suffix = "quote" if args.operation == "get_quote" else "history"
    output_path = Path(args.output_dir) / f"{safe_symbol}.{suffix}.json"
    atomic_write_handoff(output_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
