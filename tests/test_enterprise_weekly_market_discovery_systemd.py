from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "systemd" / "enterprise-weekly-market-discovery.service"
TIMER = ROOT / "systemd" / "enterprise-weekly-market-discovery.timer"


def test_weekly_discovery_timer_is_saturday_8pm_central_and_persistent():
    text = TIMER.read_text(encoding="utf-8")
    assert "OnCalendar=Sat *-*-* 20:00:00 America/Chicago" in text
    assert "Persistent=true" in text
    assert "Unit=enterprise-weekly-market-discovery.service" in text


def test_weekly_discovery_service_runs_collector_before_generator_as_tradebot():
    text = SERVICE.read_text(encoding="utf-8")
    assert "Type=oneshot" in text
    assert "User=tradebot" in text
    assert "Group=tradebot" in text
    assert "WorkingDirectory=/home/tradebot/Trade-Dividend-Bot" in text
    starts = [line for line in text.splitlines() if line.startswith("ExecStart=")]
    assert len(starts) == 5
    assert starts[0].endswith("/scripts/collect_enterprise_discovery_sources.py")
    assert starts[1].endswith("/scripts/generate_enterprise_weekly_market_discovery.py")
    assert starts[2].endswith("/scripts/generate_enterprise_dividend_income_mapping.py")
    assert starts[3].endswith("/scripts/collect_enterprise_dividend_suitability_evidence.py")
    assert starts[4].endswith("/scripts/generate_enterprise_dividend_suitability.py")


def test_weekly_discovery_service_uses_protected_credentials_and_no_swing_writes():
    text = SERVICE.read_text(encoding="utf-8")
    assert "EnvironmentFile=-/etc/tradebot/enterprise-discovery.env" in text
    assert "NoNewPrivileges=true" in text
    assert "UMask=0027" in text
    assert "TimeoutStartSec=15min" in text
    assert "Trade-Swing-Bot" not in text
    forbidden = ("robinhood", "broker", "order placement", "capital movement")
    assert all(token not in text.lower() for token in forbidden)
