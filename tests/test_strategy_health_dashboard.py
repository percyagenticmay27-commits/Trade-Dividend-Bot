"""Validate strategy-health reconciliation and alert generation."""

from __future__ import annotations

from pathlib import Path

from generate_strategy_health_dashboard import generate_dashboard


def main() -> int:
    root = Path.cwd()
    outputs = [
        root / "health_test_report.md",
        root / "health_test_strategy.csv",
        root / "health_test_pairs.csv",
    ]
    for path in outputs:
        path.unlink(missing_ok=True)
    try:
        health, pairs, alerts = generate_dashboard(
            report_path=outputs[0],
            health_path=outputs[1],
            pair_health_path=outputs[2],
        )
        row = health.iloc[0]
        assert abs(row["Current_Portfolio_Value"] - 500.0) < 0.000001
        assert abs(
            row["Current_ETF_Exposure"]
            + row["Current_SGOV_Exposure"]
            - row["Current_Portfolio_Value"]
        ) < 0.000001
        assert row["Days_Running"] == 1
        assert row["Maximum_Drawdown"] == 0.0
        assert bool(row["Within_Risk_Parameters"]) is True
        assert bool(row["Live_Deployment_Eligible"]) is False
        assert len(pairs) == 10
        assert set(pairs["Pair"]) == {
            "AMDW / AMDL", "AVGW / AVGX", "GOOW / GGLL", "NVDW / NVDX",
            "GLDW / NUGT", "NFLW / NFLU", "TSLW / TSLL", "PLTW / PLTU",
            "COIW / CONL", "MST / XXRP",
        }
        assert not any(alert.startswith("CAPITAL_RECONCILIATION") for alert in alerts)
        assert not any(alert.startswith("SGOV_MISMATCH") for alert in alerts)
        report = outputs[0].read_text(encoding="utf-8")
        assert "Future live deployment eligibility: NO" in report
        assert "PAPER ONLY" in report
    finally:
        for path in outputs:
            path.unlink(missing_ok=True)

    print("Strategy health dashboard validation: PASS")
    print("State/snapshot exposure reconciliation: PASS")
    print("Pair health coverage: PASS")
    print("Risk and live-eligibility gates: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
