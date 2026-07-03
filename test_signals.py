"""Print and save Milestone 3 signals over the downloaded period."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from signal_model_etf import generate_etf_signals
from signal_model_underlying import generate_pair_signals, generate_underlying_signals


OUTPUT_PATH = Path("signal_test_output.txt")
TEST_SERIES = [
    ("AMD", "AMD", "underlying"),
    ("NVDA", "NVDA", "underlying"),
    ("TSLA", "TSLA", "underlying"),
    ("MSTR", "MSTR", "underlying"),
]


def format_signal_rows(
    label: str,
    source: str,
    model: str,
    signals: pd.DataFrame,
) -> pd.DataFrame:
    """Return consistent printable rows for one signal test series."""
    output = signals[["Close", "EMA20", "EMA50", "RSI14", "Signal"]].copy()
    output = output.reset_index()
    output.insert(1, "label", label)
    output.insert(2, "source", source)
    output.insert(3, "model", model)
    return output


def build_test_output() -> pd.DataFrame:
    frames = []

    for label, source, model in TEST_SERIES:
        frames.append(
            format_signal_rows(
                label,
                source,
                model,
                generate_underlying_signals(source),
            )
        )

    frames.append(
        format_signal_rows(
            "MST",
            "MSTR",
            "underlying",
            generate_pair_signals("MST"),
        )
    )
    frames.append(
        format_signal_rows(
            "XXRP",
            "XXRP",
            "etf",
            generate_etf_signals("XXRP"),
        )
    )

    return pd.concat(frames, ignore_index=True)


def validate_test_output(output: pd.DataFrame) -> None:
    """Assert the approved signal rules and special mappings."""
    assert set(output["Signal"].unique()) <= {"BUY", "SELL", "HOLD"}
    assert output.groupby("label").size().eq(115).all()

    ready = output[["Close", "EMA20", "EMA50", "RSI14"]].notna().all(axis=1)
    buy = output["Signal"] == "BUY"
    sell = output["Signal"] == "SELL"

    assert (
        (output.loc[buy, "Close"] > output.loc[buy, "EMA20"])
        & (output.loc[buy, "EMA20"] > output.loc[buy, "EMA50"])
        & (output.loc[buy, "RSI14"] > 55)
    ).all()
    assert (
        (output.loc[sell, "Close"] < output.loc[sell, "EMA20"])
        | (output.loc[sell, "EMA20"] < output.loc[sell, "EMA50"])
        | (output.loc[sell, "RSI14"] < 45)
    ).all()
    assert output.loc[~ready, "Signal"].eq("HOLD").all()

    mstr = output[output["label"] == "MSTR"].reset_index(drop=True)
    mst = output[output["label"] == "MST"].reset_index(drop=True)
    pd.testing.assert_series_equal(mst["Signal"], mstr["Signal"])
    pd.testing.assert_series_equal(mst["Close"], mstr["Close"])
    assert mst["source"].eq("MSTR").all()

    xxrp = output[output["label"] == "XXRP"]
    assert xxrp["source"].eq("XXRP").all()
    assert xxrp["model"].eq("etf").all()


def main() -> int:
    output = build_test_output()
    validate_test_output(output)
    printable = output.to_csv(index=False, float_format="%.4f")
    OUTPUT_PATH.write_text(printable, encoding="utf-8")

    print(printable, end="")
    print("\nSignal counts:")
    print(output.groupby(["label", "Signal"]).size().unstack(fill_value=0))
    print("\nAssertions: PASS")
    print(f"\nSignal test output saved to: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
