"""Universe configuration for agentic ETF validation and backtests."""

START_DATE = "2026-01-01"
END_DATE = "2026-06-18"

INCOME_ETFS = [
    "AMDW",
    "GLDW",
    "NVDW",
    "GOOW",
    "NFLW",
    "AVGW",
    "COIW",
    "PLTW",
    "MST",
    "TSLW",
]

GROWTH_LEVERAGED_ETFS = [
    "AMDL",
    "NUGT",
    "NVDX",
    "GGLL",
    "NFLU",
    "AVGX",
    "CONL",
    "PLTU",
    "XXRP",
    "TSLL",
]

UNDERLYING_SIGNAL_ASSETS = [
    "AMD",
    "GLD",
    "NVDA",
    "GOOGL",
    "NFLX",
    "AVGO",
    "COIN",
    "PLTR",
    "MSTR",
    "TSLA",
]

CASH_SHIELD = ["SGOV"]

UNDERLYING_SIGNAL_MAP = {
    "AMDW": "AMD",
    "AMDL": "AMD",
    "GLDW": "GLD",
    "NUGT": "GLD",
    "NVDW": "NVDA",
    "NVDX": "NVDA",
    "GOOW": "GOOGL",
    "GGLL": "GOOGL",
    "NFLW": "NFLX",
    "NFLU": "NFLX",
    "AVGW": "AVGO",
    "AVGX": "AVGO",
    "COIW": "COIN",
    "CONL": "COIN",
    "PLTW": "PLTR",
    "PLTU": "PLTR",
    "TSLW": "TSLA",
    "TSLL": "TSLA",
    "MST": "MSTR",
}

ETF_SIGNAL_SOURCE_MAP = {
    "AMDW": "AMDW",
    "AMDL": "AMDW",
    "GLDW": "GLDW",
    "NUGT": "GLDW",
    "NVDW": "NVDW",
    "NVDX": "NVDW",
    "GOOW": "GOOW",
    "GGLL": "GOOW",
    "NFLW": "NFLW",
    "NFLU": "NFLW",
    "AVGW": "AVGW",
    "AVGX": "AVGW",
    "COIW": "COIW",
    "CONL": "COIW",
    "PLTW": "PLTW",
    "PLTU": "PLTW",
    "TSLW": "TSLW",
    "TSLL": "TSLW",
    "MST": "MST",
    "XXRP": "XXRP",
}

STANDARD_PAIRS = [
    ("AMDW", "AMDL"),
    ("GLDW", "NUGT"),
    ("NVDW", "NVDX"),
    ("GOOW", "GGLL"),
    ("NFLW", "NFLU"),
    ("AVGW", "AVGX"),
    ("COIW", "CONL"),
    ("PLTW", "PLTU"),
    ("TSLW", "TSLL"),
]

SPECIAL_INDEPENDENT_PAIR = ("MST", "XXRP")

EARNINGS_UNDERLYINGS = [
    "AMD",
    "NVDA",
    "GOOGL",
    "NFLX",
    "AVGO",
    "COIN",
    "PLTR",
    "TSLA",
    "MSTR",
]

SYMBOLS = (
    INCOME_ETFS
    + GROWTH_LEVERAGED_ETFS
    + UNDERLYING_SIGNAL_ASSETS
    + CASH_SHIELD
)
