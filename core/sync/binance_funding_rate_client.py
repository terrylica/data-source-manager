#!/usr/bin/env python
"""Client for Binance funding rate data."""

from datetime import datetime, timezone
from typing import Optional, Tuple, Union
from pathlib import Path
import pandas as pd
import time

from utils.logger_setup import logger
from utils.market_constraints import Interval, MarketType, ChartType, DataProvider
from utils.time_utils import filter_dataframe_by_time
from utils.network_utils import create_client
from utils.config import (
    FUNDING_RATE_DTYPES,
    create_empty_funding_rate_dataframe,
)
from core.sync.data_client_interface import DataClientInterface
from core.sync.cache_manager import UnifiedCacheManager


class BinanceFundingRateClient(DataClientInterface):
    """Client for retrieving funding rate data from Binance."""

    def __init__(
        self,
        symbol: str,
        interval: Union[str, Interval] = Interval.HOUR_8,
        market_type: MarketType = MarketType.FUTURES_USDT,
        use_cache: bool = True,
        cache_dir: Optional[Path] = None,
        retry_count: int = 5,
    ):
        """Initialize the Binance funding rate client.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            interval: Time interval for funding rate data
            market_type: Market type (FUTURES_USDT or FUTURES_COIN)
            use_cache: Whether to use caching
            cache_dir: Cache directory
            retry_count: Number of retries for failed requests
        """
        self._symbol = symbol.upper()

        # Handle interval as string or Interval enum
        if isinstance(interval, str):
            try:
                self._interval = Interval(interval)
            except ValueError:
                logger.warning(f"Invalid interval: {interval}, using HOUR_8")
                self._interval = Interval.HOUR_8
        else:
            self._interval = interval

        self._market_type = market_type
        self._retry_count = retry_count

        # Validate market type
        if market_type not in (MarketType.FUTURES_USDT, MarketType.FUTURES_COIN):
            raise ValueError(
                f"Invalid market type for funding rate: {market_type}. "
                f"Must be FUTURES_USDT or FUTURES_COIN."
            )

        # Set up client
        self._client = create_client()

        # Set up cache if enabled
        self._use_cache = use_cache
        if use_cache:
            if cache_dir is None:
                cache_dir = Path("./cache")
            self._cache_manager = UnifiedCacheManager(cache_dir=cache_dir)
        else:
            self._cache_manager = None

        # Set base URL based on market type
        if market_type == MarketType.FUTURES_USDT:
            self._base_url = "https://fapi.binance.com"
        else:  # MarketType.FUTURES_COIN
            self._base_url = "https://dapi.binance.com"

        logger.debug(
            f"Initialized BinanceFundingRateClient for {symbol} with "
            f"interval {interval}, market type {market_type.name}"
        )

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        # Close the HTTP client if it has a close method
        if hasattr(self._client, "close") and callable(self._client.close):
            self._client.close()

    @property
    def provider(self) -> DataProvider:
        """Get the data provider for this client."""
        return DataProvider.BINANCE

    @property
    def market_type(self) -> MarketType:
        """Get the market type for this client."""
        return self._market_type

    @property
    def chart_type(self) -> ChartType:
        """Get the chart type for this client."""
        return ChartType.FUNDING_RATE

    @property
    def symbol(self) -> str:
        """Get the trading symbol for this client."""
        return self._symbol

    @property
    def interval(self) -> Union[str, Interval]:
        """Get the interval for this client."""
        return self._interval

    def create_empty_dataframe(self) -> pd.DataFrame:
        """Create an empty DataFrame with the correct structure for funding rate data.

        Returns:
            Empty DataFrame with correct columns and types
        """
        return create_empty_funding_rate_dataframe()

    def validate_data(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """Validate that a DataFrame contains valid funding rate data.

        Args:
            df: DataFrame to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check basic structure
            required_columns = list(FUNDING_RATE_DTYPES.keys())
            missing_columns = [col for col in required_columns if col not in df.columns]

            if missing_columns:
                return False, f"Missing columns: {missing_columns}"

            # Validate data types
            for col, dtype in FUNDING_RATE_DTYPES.items():
                if col in df.columns and not pd.api.types.is_dtype_equal(
                    df[col].dtype, dtype
                ):
                    return (
                        False,
                        f"Column {col} has wrong dtype: {df[col].dtype}, expected {dtype}",
                    )

            # Additional validations
            if "funding_time" in df.columns and len(df) > 0:
                # Check if funding_time is in ascending order
                is_sorted = df["funding_time"].is_monotonic_increasing
                if not is_sorted:
                    return False, "funding_time is not in ascending order"

            return True, None
        except Exception as e:
            return False, str(e)

    def is_data_available(self, start_time: datetime, end_time: datetime) -> bool:
        """Check if funding rate data is available for the specified time range.

        Args:
            start_time: Start time
            end_time: End time

        Returns:
            True if data is available, False otherwise
        """
        # For Binance futures, funding rate data should be available from the
        # launch of the futures platform (September 2019)
        launch_date = datetime(2019, 9, 1, tzinfo=timezone.utc)

        # Check if the requested time range is after the launch date
        if end_time < launch_date:
            return False

        # Check if the requested time range is in the future
        now = datetime.now(timezone.utc)
        if start_time > now:
            return False

        # Otherwise, data should be available
        return True

    def fetch(
        self,
        symbol: Optional[str] = None,
        interval: Optional[Union[str, Interval]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        **kwargs,
    ) -> pd.DataFrame:
        """Fetch funding rate data for the specified symbol and time range.

        Args:
            symbol: Trading pair symbol (optional, defaults to instance symbol)
            interval: Time interval (optional, defaults to instance interval)
            start_time: Start time
            end_time: End time
            **kwargs: Additional parameters

        Returns:
            DataFrame with funding rate data

        Raises:
            ValueError: If parameters are invalid
        """
        # Use instance defaults if not provided
        symbol = symbol or self._symbol
        interval = interval or self._interval

        # Convert interval to Interval enum if it's a string
        if isinstance(interval, str):
            try:
                interval = Interval(interval)
            except ValueError:
                logger.warning(f"Invalid interval: {interval}, using HOUR_8")
                interval = Interval.HOUR_8

        # Validate input parameters
        if not isinstance(symbol, str) or not symbol:
            raise ValueError(f"Symbol must be a non-empty string, got {symbol}")

        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise ValueError("Start time and end time must be datetime objects")

        if start_time >= end_time:
            raise ValueError(
                f"Start time {start_time} must be before end time {end_time}"
            )

        # Use cache if enabled and available
        if self._use_cache and self._cache_manager:
            # Check if data is available in cache
            cached_df = self._cache_manager.load_from_cache(
                symbol=symbol,
                interval=interval.value,
                date=start_time,
                provider="BINANCE",
                chart_type="FUNDING_RATE",
                market_type=self._get_market_type_str(),
            )

            if cached_df is not None:
                # Filter to the requested time range
                filtered_df = filter_dataframe_by_time(
                    cached_df, start_time, end_time, "funding_time"
                )
                if not filtered_df.empty:
                    return filtered_df

        # Fetch data from API
        df = self._fetch_funding_rate(symbol, start_time, end_time)

        # Save to cache if enabled
        if self._use_cache and self._cache_manager and not df.empty:
            self._cache_manager.save_to_cache(
                df=df,
                symbol=symbol,
                interval=interval.value,
                date=start_time,
                provider="BINANCE",
                chart_type="FUNDING_RATE",
                market_type=self._get_market_type_str(),
            )

        return df

    def _get_market_type_str(self) -> str:
        """Get the market type as a string.

        Returns:
            Market type string
        """
        if self._market_type == MarketType.FUTURES_USDT:
            return "futures_usdt"
        elif self._market_type == MarketType.FUTURES_COIN:
            return "futures_coin"
        else:
            return "futures_usdt"  # Default to USDT if unknown

    def _fetch_funding_rate(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """Fetch funding rate data directly from Binance API.

        Args:
            symbol: Trading pair symbol
            start_time: Start time
            end_time: End time

        Returns:
            DataFrame with funding rate data
        """
        logger.debug(
            f"Fetching funding rate data for {symbol}: "
            f"{start_time.isoformat()} - {end_time.isoformat()}"
        )

        # Create an empty DataFrame with the correct structure
        result_df = create_empty_funding_rate_dataframe()

        # Set API endpoint based on market type
        if self._market_type == MarketType.FUTURES_USDT:
            endpoint = f"{self._base_url}/fapi/v1/fundingRate"
        else:  # MarketType.FUTURES_COIN
            endpoint = f"{self._base_url}/dapi/v1/fundingRate"

        # Convert times to milliseconds
        start_time_ms = int(start_time.timestamp() * 1000)
        end_time_ms = int(end_time.timestamp() * 1000)

        # Binance limits to 1000 records per request, so we may need multiple requests
        limit = 1000
        retry_count = 0
        current_start_ms = start_time_ms

        while current_start_ms < end_time_ms:
            try:
                # Prepare request parameters
                params = {
                    "symbol": symbol,
                    "startTime": current_start_ms,
                    "endTime": end_time_ms,
                    "limit": limit,
                }

                # Make the request
                response = self._client.get(endpoint, params=params)
                response.raise_for_status()
                data = response.json()

                if not data:
                    logger.debug(f"No more funding rate data available")
                    break

                # Process results
                for item in data:
                    funding_time = datetime.fromtimestamp(
                        int(item["fundingTime"]) / 1000, tz=timezone.utc
                    )
                    funding_rate = float(item["fundingRate"])

                    # Append to DataFrame
                    result_df = pd.concat(
                        [
                            result_df,
                            pd.DataFrame(
                                {
                                    "symbol": [symbol],
                                    "funding_time": [funding_time],
                                    "funding_rate": [funding_rate],
                                    "interval": [self._interval.value],
                                }
                            ),
                        ],
                        ignore_index=True,
                    )

                # Update start time for next batch
                if len(data) < limit:
                    # We got fewer results than requested, so we're done
                    break
                else:
                    # Use the funding time of the last record plus 1 millisecond
                    last_time = int(data[-1]["fundingTime"])
                    current_start_ms = last_time + 1

                # Reset retry counter after successful request
                retry_count = 0

            except Exception as e:
                retry_count += 1
                if retry_count > self._retry_count:
                    logger.error(
                        f"Failed to fetch funding rate data after {self._retry_count} retries: {e}"
                    )
                    break

                # Add exponential backoff with jitter
                wait_time = min(0.5 * (2**retry_count) + (0.1 * retry_count), 10)
                logger.warning(
                    f"Error fetching funding rate data (retry {retry_count}/{self._retry_count}): {e}. "
                    f"Waiting {wait_time:.2f}s before retry."
                )
                time.sleep(wait_time)

        # Sort by funding time
        if not result_df.empty:
            result_df = result_df.sort_values("funding_time").reset_index(drop=True)

            # Filter to the requested time range
            result_df = filter_dataframe_by_time(
                result_df, start_time, end_time, "funding_time"
            )

        return result_df

    def close(self) -> None:
        """Close the client and release resources."""
        if hasattr(self._client, "close") and callable(self._client.close):
            self._client.close()
