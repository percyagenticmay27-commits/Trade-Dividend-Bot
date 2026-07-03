"""Validate staged PAPER ONLY live-readiness tracking."""

from __future__ import annotations

from pathlib import Path

from generate_live_readiness_tracker import generate_live_readiness


def main() -> int:
    root = Path.cwd()
    csv_path = root / "readiness_test.csv"
    report_path = root / "readiness_test.md"
    csv_path.unlink(missing_ok=True)
    report_path.unlink(missing_ok=True)
    try:
        history, row = generate_live_readiness(
            output_path=csv_path,
            report_path=report_path,
        )
        assert len(history) == 1
        assert row["Paper_Trading_Days_Completed"] == 1
        assert row["Days_Remaining_Until_Eligibility"] == 29
        assert row["Consecutive_Clean_Validation_Days"] == 1
        assert row["Gate_30_Status"] == "IN_PROGRESS"
        assert row["Gate_60_Status"] == "IN_PROGRESS"
        assert row["Gate_90_Status"] == "IN_PROGRESS"
        assert row["Gate_30_Days_Remaining"] == 29
        assert row["Gate_60_Days_Remaining"] == 59
        assert row["Gate_90_Days_Remaining"] == 89
        assert abs(row["Overall_Live_Readiness_Pct"] - 1.111111) < 0.000001

        duplicate_history, duplicate_row = generate_live_readiness(
            output_path=csv_path,
            report_path=report_path,
        )
        assert len(duplicate_history) == 1
        assert duplicate_row["Consecutive_Clean_Validation_Days"] == 1
        report = report_path.read_text(encoding="utf-8")
        assert "1.111111% complete" in report
        assert "PAPER ONLY" in report
    finally:
        csv_path.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)

    print("Live readiness tracker validation: PASS")
    print("30/60/90-day gate calculations: PASS")
    print("Same-date idempotency: PASS")
    print("Overall readiness percentage: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
