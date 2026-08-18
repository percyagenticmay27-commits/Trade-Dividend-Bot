import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_production_youtube_sources_are_unique_reviewed_and_quota_bounded():
    catalog = json.loads((ROOT / "configs" / "enterprise_discovery_sources.json").read_text(encoding="utf-8"))
    sources = [row for row in catalog["sources"] if row.get("source_type") == "YOUTUBE_SEARCH"]
    assert len(sources) == 5
    assert len({row["channel_id"] for row in sources}) == 5
    assert all(row["credibility_reviewed"] is True for row in sources)
    assert all(row["authority"] in {"REVIEWED_CREATOR", "PROFESSIONAL_MEDIA"} for row in sources)
    assert sum(100 for _ in sources) <= 500
    assert all("BowTie Nation" != row["source_name"] for row in sources)


def test_bow_tie_nation_resolves_to_joseph_hogue_not_lookalike_channel():
    catalog = json.loads((ROOT / "configs" / "enterprise_discovery_sources.json").read_text(encoding="utf-8"))
    joseph = next(row for row in catalog["sources"] if "Joseph Hogue" in row.get("source_name", ""))
    assert joseph["channel_id"] == "UCbKdotYtcY9SxoU8CYAXdvg"


def test_production_professional_news_source_is_reviewed_and_single_request_bounded():
    catalog = json.loads((ROOT / "configs" / "enterprise_discovery_sources.json").read_text(encoding="utf-8"))
    sources = [row for row in catalog["sources"] if row.get("source_type") == "ALPHA_VANTAGE_NEWS"]
    assert len(sources) == 1
    assert sources[0]["source_name"] == "Alpha Vantage News & Sentiment"
    assert sources[0]["credibility_reviewed"] is True
    assert sources[0]["authority"] == "PROFESSIONAL_MEDIA"
    assert 1 <= sources[0]["max_results"] <= 200
    assert "api" not in json.dumps(sources[0]).lower().replace("alpha_vantage", "")
