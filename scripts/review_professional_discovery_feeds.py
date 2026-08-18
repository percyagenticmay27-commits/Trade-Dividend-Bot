#!/usr/bin/env python3
"""Read-only review of candidate professional RSS/Atom discovery feeds."""
from __future__ import annotations

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from enterprise_discovery_source_collector import _recent_feed_evidence, fetch_professional_url


def _get(url: str, user_agent: str) -> bytes:
    return fetch_professional_url(url, user_agent)


def review_feed(
    source_name: str,
    url: str,
    *,
    user_agent: str,
    get_bytes: Callable[[str, str], bytes] = _get,
    today: date | None = None,
) -> dict:
    if not str(user_agent).strip():
        raise ValueError("AI_CIO_DISCOVERY_USER_AGENT is required")
    if not str(url).lower().startswith("https://"):
        raise ValueError("professional feed review URL must use HTTPS")
    try:
        payload = get_bytes(url, user_agent)
    except OSError as exc:
        return {
            "source_name": source_name,
            "url": url,
            "review_status": "REQUEST_FAILED",
            "xml_feed_valid": False,
            "entry_count": 0,
            "recent_entry_count": 0,
            "sample_recent_entries": [],
            "review_error": f"{type(exc).__name__}: {exc}",
            "automatically_approved": False,
            "production_configuration_modified": False,
        }
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        return {
            "source_name": source_name,
            "url": url,
            "review_status": "INVALID_XML",
            "xml_feed_valid": False,
            "entry_count": 0,
            "recent_entry_count": 0,
            "sample_recent_entries": [],
            "review_error": f"ParseError: {exc}",
            "automatically_approved": False,
            "production_configuration_modified": False,
        }
    entries = list(root.findall(".//item")) + list(root.findall(".//{*}entry"))
    cutoff = (today or date.today()) - timedelta(days=7)
    recent = _recent_feed_evidence(payload, {
        "source_name": source_name,
        "producer": source_name,
        "source_class": "PROFESSIONAL_MEDIA",
    }, cutoff)
    return {
        "source_name": source_name,
        "url": url,
        "review_status": "VALID_WITH_RECENT_ENTRIES" if recent else "VALID_NO_RECENT_ENTRIES",
        "xml_feed_valid": True,
        "entry_count": len(entries),
        "recent_entry_count": len(recent),
        "sample_recent_entries": [
            {
                "title": row.get("title"),
                "mentioned_on": row.get("mentioned_on"),
                "source_url": row.get("source_url"),
            }
            for row in recent[:5]
        ],
        "automatically_approved": False,
        "production_configuration_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-name", required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument(
        "--output",
        default=str(ROOT / "artifacts" / "discovery" / "professional_feed_review.json"),
    )
    args = parser.parse_args()
    result = review_feed(
        args.source_name,
        args.url,
        user_agent=os.environ.get("AI_CIO_DISCOVERY_USER_AGENT", ""),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Professional feed review written: {output}")
    print(f"Status: {result['review_status']}")
    print(f"Entries: {result['entry_count']}; recent: {result['recent_entry_count']}")
    print("Production configuration modified: False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
