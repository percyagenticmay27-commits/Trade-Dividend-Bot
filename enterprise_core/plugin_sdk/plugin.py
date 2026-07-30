"""Version 1 strategy plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import PluginContext, PluginRunResult


class EnterpriseStrategyPlugin(ABC):
    """Public strategy boundary used by Enterprise Core.

    Implementations remain paper-only and may access shared capabilities only
    through the service objects supplied in PluginContext/ServiceRegistry.
    """

    paper_trade_mode = True
    live_trading_enabled = False
    broker_execution_enabled = False

    @property
    @abstractmethod
    def strategy_id(self) -> str:
        """Return the stable strategy identifier."""

    @abstractmethod
    def initialize(self, context: PluginContext) -> None:
        """Initialize the plugin without running strategy logic."""

    @abstractmethod
    def run(self) -> PluginRunResult:
        """Run one paper-only strategy cycle."""

    def shutdown(self) -> None:
        """Release strategy-owned resources. Default implementation is a no-op."""
