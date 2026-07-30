"""Append-only JSON Lines persistence for Enterprise Events."""

from __future__ import annotations

import json
from pathlib import Path

from .models import EnterpriseEvent


class JsonLinesEventStore:
    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, event: EnterpriseEvent) -> Path:
        event.validate()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
        return self.path

    def read_all(self) -> tuple[EnterpriseEvent, ...]:
        if not self.path.exists():
            return ()
        events: list[EnterpriseEvent] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    raise ValueError("event root must be an object")
                events.append(EnterpriseEvent.from_dict(payload))
            except (json.JSONDecodeError, ValueError, TypeError) as exc:
                raise ValueError(f"invalid event at line {line_number}: {exc}") from exc
        return tuple(events)
