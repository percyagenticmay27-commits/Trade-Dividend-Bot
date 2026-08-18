#!/usr/bin/env python3
"""Create a human-review report for candidate YouTube discovery channels.

This utility never edits the production source catalog. Search results are
untrusted candidates until an operator verifies the channel identity.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
SEED_QUERIES = (
    "Bow Tie Nation",
    "Earn Your Leisure",
    "BWB Business With Brian",
    "Let's Talk Money Joseph Hogue CFA",
    "CBS News business markets",
    "Ticker Symbol YOU",
)


def search_channel_candidates(api_key: str, queries=SEED_QUERIES, *, get_json=None) -> dict:
    if not str(api_key).strip():
        raise ValueError("YOUTUBE_API_KEY is required")

    def default_get(url: str) -> dict:
        request = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=30) as response:  # nosec B310: fixed Google API endpoint
            return json.loads(response.read().decode("utf-8"))

    getter = get_json or default_get
    searches = []
    for query in queries:
        params = urllib.parse.urlencode({
            "part": "snippet",
            "type": "channel",
            "maxResults": "5",
            "q": query,
            "key": api_key,
        })
        payload = getter(f"{YOUTUBE_SEARCH_URL}?{params}")
        candidates = []
        for item in payload.get("items", []) if isinstance(payload, dict) else []:
            identifier = item.get("id") if isinstance(item, dict) else None
            snippet = item.get("snippet") if isinstance(item, dict) else None
            channel_id = identifier.get("channelId") if isinstance(identifier, dict) else None
            if not channel_id or not isinstance(snippet, dict):
                continue
            candidates.append({
                "channel_id": channel_id,
                "channel_title": str(snippet.get("channelTitle") or snippet.get("title") or ""),
                "description": str(snippet.get("description") or ""),
                "channel_url": f"https://www.youtube.com/channel/{channel_id}",
                "review_status": "UNVERIFIED",
            })
        searches.append({"seed_query": query, "candidates": candidates})
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "purpose": "HUMAN_CHANNEL_IDENTITY_REVIEW_ONLY",
        "automatically_approved": False,
        "searches": searches,
    }


def main() -> int:
    report = search_channel_candidates(os.environ.get("YOUTUBE_API_KEY", ""))
    output = ROOT / "artifacts" / "discovery" / "youtube_channel_review.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"YouTube channel review written: {output}")
    for search in report["searches"]:
        print(f"\n{search['seed_query']}")
        for index, candidate in enumerate(search["candidates"], 1):
            print(f"  {index}. {candidate['channel_title']} | {candidate['channel_id']} | {candidate['channel_url']}")
    print("\nNo channel was automatically approved or added to production configuration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
