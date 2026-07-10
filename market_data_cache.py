"""Local JSON cache for read-only market data.

The cache stores provider responses with timestamps and supports stale-data fallback.
It never communicates with brokerage systems and never performs trading actions.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

MODULE_NAME = "market_data_cache"
MODULE_VERSION = "1.0.0"
DEFAULT_CACHE_DIR = "cache/market_data"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_key(namespace: str, key: str) -> str:
    digest = hashlib.sha256(f"{namespace}:{key}".encode("utf-8")).hexdigest()
    return f"{namespace}_{digest}.json"


class MarketDataCache:
    def __init__(self, root_path: str = ".", cache_dir: str = DEFAULT_CACHE_DIR) -> None:
        self.root = Path(root_path) / cache_dir

    def _path(self, namespace: str, key: str) -> Path:
        return self.root / _safe_key(namespace, key)

    def write(self, namespace: str, key: str, payload: Mapping[str, Any]) -> Path:
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {
            "namespace": namespace,
            "key": key,
            "cached_at_utc": utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "payload": dict(payload),
        }
        path.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def read(self, namespace: str, key: str, max_age_seconds: Optional[int] = None) -> Optional[dict[str, Any]]:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
                return None
            cached_at = str(envelope.get("cached_at_utc", ""))
            if max_age_seconds is not None:
                timestamp = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
                age = (utc_now() - timestamp).total_seconds()
                if age > max_age_seconds:
                    return None
            return dict(envelope["payload"])
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return None

    def read_stale(self, namespace: str, key: str) -> Optional[dict[str, Any]]:
        return self.read(namespace, key, max_age_seconds=None)
