"""Enterprise compatibility integrations for existing paper-only strategies."""

from .dividend_bot import (
    DIVIDEND_STRATEGY_ID,
    DIVIDEND_STRATEGY_NAME,
    DividendBotEnterprisePlugin,
    DividendContractPaths,
)

__all__ = [
    "DIVIDEND_STRATEGY_ID",
    "DIVIDEND_STRATEGY_NAME",
    "DividendBotEnterprisePlugin",
    "DividendContractPaths",
]
