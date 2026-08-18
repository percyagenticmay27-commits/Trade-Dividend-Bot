import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "review_youtube_discovery_channels.py"


def _module():
    spec = importlib.util.spec_from_file_location("review_youtube_discovery_channels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_channel_search_results_remain_unverified_and_do_not_edit_configuration():
    module = _module()
    requested = []
    payload = {"items": [{
        "id": {"channelId": "UC123"},
        "snippet": {"channelTitle": "Candidate Channel", "description": "Financial education"},
    }]}
    report = module.search_channel_candidates(
        "secret-key", ["Candidate"], get_json=lambda url: requested.append(url) or payload,
    )
    candidate = report["searches"][0]["candidates"][0]
    assert report["automatically_approved"] is False
    assert candidate["review_status"] == "UNVERIFIED"
    assert candidate["channel_url"] == "https://www.youtube.com/channel/UC123"
    assert "type=channel" in requested[0]
    assert "maxResults=5" in requested[0]


def test_channel_review_requires_api_key():
    module = _module()
    try:
        module.search_channel_candidates("")
    except ValueError as exc:
        assert "YOUTUBE_API_KEY" in str(exc)
    else:
        raise AssertionError("missing API key must fail closed")
