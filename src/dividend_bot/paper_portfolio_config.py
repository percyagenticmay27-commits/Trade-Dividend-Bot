"""Approved Strength Weighted Hybrid configuration for paper trading."""

from __future__ import annotations


PAPER_ONLY = True
TOTAL_PAPER_CAPITAL = 500.0
INITIAL_A_WEIGHT = 0.70
INITIAL_B_WEIGHT = 0.30

PAIR_MANAGED = "pair_managed"
INDEPENDENT_SLEEVES = "independent_sleeves"

PAPER_PAIRS = {
    "AMDW / AMDL": {
        "a": "AMDW", "b": "AMDL", "allocation": 75.0,
        "architecture": PAIR_MANAGED, "a_signal": "AMD", "b_signal": "AMD",
        "earnings_source": "AMD", "b_follows_earnings": True,
    },
    "AVGW / AVGX": {
        "a": "AVGW", "b": "AVGX", "allocation": 60.0,
        "architecture": PAIR_MANAGED, "a_signal": "AVGO", "b_signal": "AVGO",
        "earnings_source": "AVGO", "b_follows_earnings": True,
    },
    "GOOW / GGLL": {
        "a": "GOOW", "b": "GGLL", "allocation": 60.0,
        "architecture": INDEPENDENT_SLEEVES, "a_signal": "GOOW", "b_signal": "GGLL",
        "earnings_source": "GOOGL", "b_follows_earnings": True,
    },
    "NVDW / NVDX": {
        "a": "NVDW", "b": "NVDX", "allocation": 55.0,
        "architecture": PAIR_MANAGED, "a_signal": "NVDA", "b_signal": "NVDA",
        "earnings_source": "NVDA", "b_follows_earnings": True,
    },
    "GLDW / NUGT": {
        "a": "GLDW", "b": "NUGT", "allocation": 50.0,
        "architecture": PAIR_MANAGED, "a_signal": "GLD", "b_signal": "GLD",
        "earnings_source": None, "b_follows_earnings": False,
    },
    "NFLW / NFLU": {
        "a": "NFLW", "b": "NFLU", "allocation": 50.0,
        "architecture": PAIR_MANAGED, "a_signal": "NFLX", "b_signal": "NFLX",
        "earnings_source": "NFLX", "b_follows_earnings": True,
    },
    "TSLW / TSLL": {
        "a": "TSLW", "b": "TSLL", "allocation": 45.0,
        "architecture": PAIR_MANAGED, "a_signal": "TSLA", "b_signal": "TSLA",
        "earnings_source": "TSLA", "b_follows_earnings": True,
    },
    "PLTW / PLTU": {
        "a": "PLTW", "b": "PLTU", "allocation": 40.0,
        "architecture": PAIR_MANAGED, "a_signal": "PLTR", "b_signal": "PLTR",
        "earnings_source": "PLTR", "b_follows_earnings": True,
    },
    "COIW / CONL": {
        "a": "COIW", "b": "CONL", "allocation": 35.0,
        "architecture": INDEPENDENT_SLEEVES, "a_signal": "COIW", "b_signal": "CONL",
        "earnings_source": "COIN", "b_follows_earnings": True,
    },
    "MST / XXRP": {
        "a": "MST", "b": "XXRP", "allocation": 30.0,
        "architecture": INDEPENDENT_SLEEVES, "a_signal": "MSTR", "b_signal": "XXRP",
        "earnings_source": "MSTR", "b_follows_earnings": False,
    },
}


def validate_paper_config() -> None:
    """Reject configuration drift before a paper ledger is initialized."""
    assert PAPER_ONLY is True
    assert abs(sum(item["allocation"] for item in PAPER_PAIRS.values()) - 500.0) < 1e-9
    assert sum(item["architecture"] == PAIR_MANAGED for item in PAPER_PAIRS.values()) == 7
    assert sum(
        item["architecture"] == INDEPENDENT_SLEEVES
        for item in PAPER_PAIRS.values()
    ) == 3


validate_paper_config()
