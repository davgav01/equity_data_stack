"""Provider interfaces for market data sources."""

from abc import ABC, abstractmethod
from datetime import date

import pandas as pd


class ProviderInterface(ABC):
    """Abstract interface for data providers."""

    @abstractmethod
    def get_bars(
        self,
        symbol_universe: list[str],
        trading_day: date,
        freq: str,
    ) -> pd.DataFrame:
        """Return bar data for the requested universe and trading day."""

    @abstractmethod
    def get_securities(self) -> pd.DataFrame:
        """Return the security master table."""

    @abstractmethod
    def get_splits(
        self, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        """Return split events, optionally filtered by date."""

    @abstractmethod
    def get_dividends(
        self, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        """Return dividend events, optionally filtered by date."""
