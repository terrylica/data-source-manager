#!/usr/bin/env python
"""Interface for data clients."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Tuple, Union
import pandas as pd

from utils.market_constraints import DataProvider, ChartType


class DataClientInterface(ABC):
    """Interface for data clients to implement.

    This abstract base class defines the common interface that all data clients
    must implement to be used with the DataSourceManager.
    """

    @property
    @abstractmethod
    def provider(self) -> DataProvider:
        """Get the data provider.

        Returns:
            The data provider (e.g., BINANCE)
        """

    @property
    @abstractmethod
    def chart_type(self) -> ChartType:
        """Get the chart type.

        Returns:
            The chart type (e.g., KLINES, FUNDING_RATE)
        """

    @property
    @abstractmethod
    def symbol(self) -> str:
        """Get the symbol.

        Returns:
            The trading pair symbol
        """

    @property
    @abstractmethod
    def interval(self) -> Union[str, object]:
        """Get the interval.

        Returns:
            The time interval
        """

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch data from the data source.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            start_time: Start time
            end_time: End time
            **kwargs: Additional parameters

        Returns:
            DataFrame with the fetched data
        """

    @abstractmethod
    def is_data_available(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if data is available for the specified time range.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            True if data is available, False otherwise
        """

    @abstractmethod
    def create_empty_dataframe(self) -> pd.DataFrame:
        """Create an empty DataFrame with the correct structure.

        Returns:
            Empty DataFrame
        """

    @abstractmethod
    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Validate that a DataFrame contains valid data.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (is_valid, error_message)
        """

    @abstractmethod
    def close(self) -> None:
        """Close the client and release resources."""
