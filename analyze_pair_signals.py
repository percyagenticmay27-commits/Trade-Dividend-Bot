"""Analyze signal distribution for configured ETF pairs and special components."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from pairs_config import STANDARD_PAIRS
from signal_model_etf import generate_etf_signals
from signal_model_underlying import (
    generate_pair_signals,
    get_underlying_signal_source,
)


OUTPUT_PATH = Path("pair_signal_analysis.csv")
CONCENTRATION_THRESHOLD = 95.0


def first_signal_date(signals: pd.DataFrame, signal: str) -> str:
    """Return the first date for a signal, or an empty string when absent."""
    matching_dates = signals.index[signals["Signal"] == signal]
    if matching_dates.empty:
        return ""
    return pd.Timestamp(matching_dates.min()).strftime("%Y-%m-%d")


def summarize_signal_stream(
    pair_label: str,
    signal_source: str,
    signal_model: str,
    signals: pd.DataFrame,
) -> dict[str, object]:
    """Summarize BUY/SELL/HOLD counts and concentration for one stream."""
    counts = signals["Signal"].value_counts()
    total_days = len(signals)
    buy_days = int(counts.get("BUY", 0))
    sell_days = int(counts.get("SELL", 0))
    hold_days = int(counts.get("HOLD", 0))

    buy_percent = (buy_days / total_days * 100) if total_days else 0.0
    sell_percent = (sell_days / total_days * 100) if total_days else 0.0
    hold_percent = (hold_days / total_days * 100) if total_days else 0.0

    if buy_percent >= CONCENTRATION_THRESHOLD:
        concentration = "95%+ BUY"
    elif sell_percent >= CONCENTRATION_THRESHOLD:
        concentration = "95%+ SELL"
    else:
        concentration = ""

    return {
        "Pair": pair_label,
        "Signal Source": signal_source,
        "Signal Model": signal_model,
        "BUY Days": buy_days,
        "SELL Days": sell_days,
        "HOLD Days": hold_days,
        "First BUY": first_signal_date(signals, "BUY"),
        "First SELL": first_signal_date(signals, "SELL"),
        "BUY Percent": round(buy_percent, 2),
        "SELL Percent": round(sell_percent, 2),
        "HOLD Percent": round(hold_percent, 2),
        "Concentration": concentration,
    }


def build_pair_analysis() -> pd.DataFrame:
    """Build standard pair rows plus independent MST and XXRP rows."""
    rows = []

    for left, right in STANDARD_PAIRS:
        source = get_underlying_signal_source(left)
        rows.append(
            summarize_signal_stream(
                pair_label=f"{left} / {right}",
                signal_source=source,
                signal_model="underlying",
                signals=generate_pair_signals(left),
            )
        )

    rows.append(
        summarize_signal_stream(
            pair_label="MST / XXRP - MST",
            signal_source="MSTR",
            signal_model="underlying",
            signals=generate_pair_signals("MST"),
        )
    )
    rows.append(
        summarize_signal_stream(
            pair_label="MST / XXRP - XXRP",
            signal_source="XXRP",
            signal_model="etf",
            signals=generate_etf_signals("XXRP"),
        )
    )

    return pd.DataFrame(rows)


def validate_analysis(analysis: pd.DataFrame) -> None:
    """Validate row coverage and daily count totals."""
    assert len(analysis) == 11
    assert (
        analysis[["BUY Days", "SELL Days", "HOLD Days"]].sum(axis=1) == 115
    ).all()
    assert analysis["Pair"].str.contains("MST / XXRP").sum() == 2
    assert (
        analysis[["BUY Percent", "SELL Percent", "HOLD Percent"]]
        .sum(axis=1)
        .between(99.99, 100.01)
    ).all()


def main() -> int:
    analysis = build_pair_analysis()
    validate_analysis(analysis)
    analysis.to_csv(OUTPUT_PATH, index=False)

    print(analysis.to_string(index=False))
    print("\nAssertions: PASS")

    concentrated = analysis[analysis["Concentration"] != ""]
    if concentrated.empty:
        print("95% concentration check: no pair is 95%+ BUY or 95%+ SELL")
    else:
        print("\n95% concentration warnings:")
        print(concentrated[["Pair", "Concentration"]].to_string(index=False))

    print(f"\nPair analysis saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
