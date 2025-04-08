#!/usr/bin/env python
"""Data source manager that mediates between different data sources."""

from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, Any, List, Union, TypeVar, Type
from enum import Enum, auto
import pandas as pd
from pathlib import Path
import asyncio
import gc
import os
from dataclasses import dataclass, field
import math
import random
import inspect
import traceback

from utils.logger_setup import logger
from utils.market_constraints import Interval, MarketType, ChartType, DataProvider
from utils.time_utils import (
    filter_dataframe_by_time,
    align_time_boundaries,
)
from utils.validation import DataFrameValidator, DataValidation
from utils.async_cleanup import direct_resource_cleanup
from utils.config import (
    OUTPUT_DTYPES,
    FUNDING_RATE_DTYPES,
    VISION_DATA_DELAY_HOURS,
    REST_CHUNK_SIZE,
    REST_MAX_CHUNKS,
    API_TIMEOUT,
    standardize_column_names,
    create_empty_dataframe,
    create_empty_funding_rate_dataframe,
    MAX_TIMEOUT,
)
from core.rest_data_client import RestDataClient
from core.vision_data_client import VisionDataClient
from core.binance_funding_rate_client import BinanceFundingRateClient
from core.cache_manager import UnifiedCacheManager
from core.data_client_factory import DataClientFactory
from core.data_client_interface import DataClientInterface


class DataSource(Enum):
    """Enum for data source selection."""

    AUTO = auto()  # Automatically select best source
    REST = auto()  # Force REST API
    VISION = auto()  # Force Vision API


T = TypeVar("T")


@dataclass
class DataSourceConfig:
    """Configuration for DataSourceManager.

    This class provides a convenient way to configure the DataSourceManager
    with clear parameter documentation and defaults.

    Attributes:
        market_type (MarketType): Market type (SPOT, FUTURES_USDT, FUTURES_COIN).
            Mandatory parameter that determines which market data to retrieve.
        provider (DataProvider): Data provider (currently only BINANCE is supported).
            Default is BINANCE.
        chart_type (ChartType): Chart type (KLINES, FUNDING_RATE).
            Default is KLINES (candlestick data).
        cache_dir (Optional[Path]): Directory to store cache files.
            Default is './cache'. Set to None to disable caching.
        use_cache (bool): Whether to use caching.
            Default is True. Set to False to always fetch fresh data.
        max_concurrent (int): Maximum number of concurrent requests.
            Default is 50. Adjust based on your network capabilities.
        retry_count (int): Number of retries for failed requests.
            Default is 5. Increase for less stable networks.
        max_concurrent_downloads (Optional[int]): Maximum concurrent downloads for Vision API.
            Default is None (uses system default). Lower for limited bandwidth.
        cache_expires_minutes (int): Cache expiration time in minutes.
            Default is 60 minutes. Increase for less frequently updated data.
        use_httpx (bool): Whether to use httpx instead of curl_cffi for HTTP clients.
            Default is False. Set to True if experiencing issues with curl_cffi.
        rest_client (Optional[RestDataClient]): Optional external REST API client.
            Default is None (auto-created). Only provide if you need custom REST client behavior.
        vision_client (Optional[VisionDataClient]): Optional external Vision API client.
            Default is None (auto-created). Only provide if you need custom Vision API behavior.
    """

    # Mandatory parameters
    market_type: MarketType

    # Optional parameters with defaults
    provider: DataProvider = DataProvider.BINANCE
    chart_type: ChartType = ChartType.KLINES
    cache_dir: Optional[Path] = None
    use_cache: bool = True
    max_concurrent: int = 50
    retry_count: int = 5
    max_concurrent_downloads: Optional[int] = None
    cache_expires_minutes: int = 60
    use_httpx: bool = False

    # Advanced parameters (rarely need to be changed)
    rest_client: Optional[RestDataClient] = None
    vision_client: Optional[VisionDataClient] = None

    def __post_init__(self):
        """Validate parameters after initialization."""
        if not isinstance(self.market_type, MarketType):
            raise TypeError(
                f"market_type must be a MarketType enum, got {type(self.market_type)}"
            )

        if not isinstance(self.provider, DataProvider):
            raise TypeError(
                f"provider must be a DataProvider enum, got {type(self.provider)}"
            )

        if not isinstance(self.chart_type, ChartType):
            raise TypeError(
                f"chart_type must be a ChartType enum, got {type(self.chart_type)}"
            )

        if self.cache_dir is not None and not isinstance(self.cache_dir, Path):
            self.cache_dir = Path(str(self.cache_dir))

        if self.max_concurrent <= 0:
            raise ValueError(f"max_concurrent must be > 0, got {self.max_concurrent}")

        if self.retry_count < 0:
            raise ValueError(f"retry_count must be >= 0, got {self.retry_count}")

        if (
            self.max_concurrent_downloads is not None
            and self.max_concurrent_downloads <= 0
        ):
            raise ValueError(
                f"max_concurrent_downloads must be > 0, got {self.max_concurrent_downloads}"
            )

        if self.cache_expires_minutes <= 0:
            raise ValueError(
                f"cache_expires_minutes must be > 0, got {self.cache_expires_minutes}"
            )

    @classmethod
    def create(cls: Type[T], market_type: MarketType, **kwargs) -> T:
        """Create a DataSourceConfig with the given market_type and optional overrides.

        This is a convenience builder method that allows for a more fluent interface.

        Args:
            market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
            **kwargs: Optional parameter overrides

        Returns:
            Configured DataSourceConfig instance

        Raises:
            TypeError: If market_type is not a MarketType enum
            ValueError: If any parameter values are invalid

        Examples:
            # Basic config for SPOT market
            config = DataSourceConfig.create(MarketType.SPOT)

            # Config for FUTURES with custom cache directory and HTTP client
            config = DataSourceConfig.create(
                MarketType.FUTURES_USDT,
                cache_dir=Path("./my_cache"),
                use_httpx=True
            )
        """
        if not isinstance(market_type, MarketType):
            raise TypeError(
                f"market_type must be a MarketType enum, got {type(market_type)}"
            )
        return cls(market_type=market_type, **kwargs)


@dataclass
class DataQueryConfig:
    """Configuration for data queries in the DataSourceManager.

    This class provides a clear way to specify parameters for the get_data method.

    Attributes:
        symbol (str): Trading pair symbol (e.g., "BTCUSDT").
            Mandatory parameter specifying which trading pair to retrieve data for.
        start_time (datetime): Start time for data retrieval.
            Mandatory parameter. Must be timezone-aware (preferably UTC).
        end_time (datetime): End time for data retrieval.
            Mandatory parameter. Must be timezone-aware (preferably UTC).
        interval (Interval): Time interval between data points.
            Default is SECOND_1. Options vary by market type.
        use_cache (bool): Whether to use cache for this specific query.
            Default is True. Override to fetch fresh data for this query only.
        enforce_source (DataSource): Force specific data source.
            Default is AUTO (smart selection). Override to force REST or VISION API.
        provider (Optional[DataProvider]): Override provider for this query.
            Default is None (use the DataSourceManager's provider).
        chart_type (Optional[ChartType]): Override chart type for this query.
            Default is None (use the DataSourceManager's chart type).
    """

    # Mandatory parameters
    symbol: str
    start_time: datetime
    end_time: datetime

    # Optional parameters with defaults
    interval: Interval = Interval.SECOND_1
    use_cache: bool = True
    enforce_source: DataSource = DataSource.AUTO

    # Override parameters
    provider: Optional[DataProvider] = None
    chart_type: Optional[ChartType] = None

    def __post_init__(self):
        """Validate parameters after initialization."""
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError(f"symbol must be a non-empty string, got {self.symbol}")

        if not isinstance(self.start_time, datetime):
            raise TypeError(
                f"start_time must be a datetime object, got {type(self.start_time)}"
            )

        if not isinstance(self.end_time, datetime):
            raise TypeError(
                f"end_time must be a datetime object, got {type(self.end_time)}"
            )

        # Check if datetimes are timezone-aware
        if self.start_time.tzinfo is None:
            raise ValueError("start_time must be timezone-aware")

        if self.end_time.tzinfo is None:
            raise ValueError("end_time must be timezone-aware")

        if self.start_time >= self.end_time:
            raise ValueError(
                f"start_time ({self.start_time}) must be before end_time ({self.end_time})"
            )

        if not isinstance(self.interval, Interval):
            raise TypeError(
                f"interval must be an Interval enum, got {type(self.interval)}"
            )

        if not isinstance(self.enforce_source, DataSource):
            raise TypeError(
                f"enforce_source must be a DataSource enum, got {type(self.enforce_source)}"
            )

        if self.provider is not None and not isinstance(self.provider, DataProvider):
            raise TypeError(
                f"provider must be a DataProvider enum or None, got {type(self.provider)}"
            )

        if self.chart_type is not None and not isinstance(self.chart_type, ChartType):
            raise TypeError(
                f"chart_type must be a ChartType enum or None, got {type(self.chart_type)}"
            )

        # Convert symbol to uppercase for consistency
        self.symbol = self.symbol.upper()

    @classmethod
    def create(
        cls: Type[T], symbol: str, start_time: datetime, end_time: datetime, **kwargs
    ) -> T:
        """Create a DataQueryConfig with required parameters and optional overrides.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            start_time: Start time for data retrieval (timezone-aware)
            end_time: End time for data retrieval (timezone-aware)
            **kwargs: Optional parameter overrides

        Returns:
            Configured DataQueryConfig instance

        Raises:
            ValueError: If symbol is empty or start_time >= end_time
            TypeError: If parameters have incorrect types

        Examples:
            # Basic query for Bitcoin hourly data
            query = DataQueryConfig.create(
                "BTCUSDT",
                datetime(2023, 1, 1, tzinfo=timezone.utc),
                datetime(2023, 1, 2, tzinfo=timezone.utc),
                interval=Interval.HOUR_1
            )

            # Query with forced Vision API usage
            query = DataQueryConfig.create(
                "ETHUSDT",
                start_time,
                end_time,
                enforce_source=DataSource.VISION
            )
        """
        if not symbol:
            raise ValueError("symbol cannot be empty")

        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise TypeError("start_time and end_time must be datetime objects")

        if start_time >= end_time:
            raise ValueError(
                f"start_time ({start_time}) must be before end_time ({end_time})"
            )

        return cls(symbol=symbol, start_time=start_time, end_time=end_time, **kwargs)


class DataSourceManager:
    """Mediator between data sources with smart selection and caching.

    This class serves as the central point for:
    1. Data source selection between different providers and APIs
    2. Unified caching strategy across all data sources
    3. Cache integrity validation and management
    4. Data format standardization
    """

    # Vision API constraints - using imported constant
    VISION_DATA_DELAY_HOURS = VISION_DATA_DELAY_HOURS

    # REST API constraints - using imported constants
    REST_CHUNK_SIZE = REST_CHUNK_SIZE
    REST_MAX_CHUNKS = REST_MAX_CHUNKS

    # Output format specification from centralized config
    OUTPUT_DTYPES = OUTPUT_DTYPES.copy()
    FUNDING_RATE_DTYPES = FUNDING_RATE_DTYPES.copy()

    # Default market type that can be configured globally
    DEFAULT_MARKET_TYPE = MarketType.SPOT

    @classmethod
    def get_output_format(
        cls, chart_type: ChartType = ChartType.KLINES
    ) -> Dict[str, str]:
        """Get the standardized output format specification.

        Args:
            chart_type: Type of chart data

        Returns:
            Dictionary mapping column names to their dtypes

        Note:
            - Index is always pd.DatetimeIndex in UTC timezone
            - All timestamps are aligned to interval boundaries
            - Empty DataFrames maintain this structure
        """
        if chart_type == ChartType.FUNDING_RATE:
            return cls.FUNDING_RATE_DTYPES.copy()
        return cls.OUTPUT_DTYPES.copy()

    @classmethod
    def create(cls, market_type: Optional[MarketType] = None, **kwargs):
        """Create a DataSourceManager with a more Pythonic interface.

        This factory method provides a cleaner way to instantiate the DataSourceManager
        with proper default values and documentation.

        Args:
            market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
                If None, uses the class's DEFAULT_MARKET_TYPE
            **kwargs: Additional parameters as needed

        Returns:
            Initialized DataSourceManager

        Examples:
            # Create a basic manager with default market type
            manager = DataSourceManager.create()

            # Create a manager for spot market
            manager = DataSourceManager.create(MarketType.SPOT)

            # Create a manager for futures with custom settings
            manager = DataSourceManager.create(
                MarketType.FUTURES_USDT,
                chart_type=ChartType.FUNDING_RATE,
                cache_dir=Path("./my_cache"),
                use_httpx=True
            )
        """
        # Use the configured default market type if none provided
        if market_type is None:
            market_type = cls.DEFAULT_MARKET_TYPE
            logger.debug(f"Using default market type: {market_type.name}")

        config = DataSourceConfig.create(market_type, **kwargs)
        return cls(
            market_type=config.market_type,
            provider=config.provider,
            chart_type=config.chart_type,
            cache_dir=config.cache_dir,
            use_cache=config.use_cache,
            max_concurrent=config.max_concurrent,
            retry_count=config.retry_count,
            max_concurrent_downloads=config.max_concurrent_downloads,
            cache_expires_minutes=config.cache_expires_minutes,
            use_httpx=config.use_httpx,
            rest_client=config.rest_client,
            vision_client=config.vision_client,
        )

    @classmethod
    def configure_defaults(cls, market_type: MarketType) -> None:
        """Configure default market type for all DataSourceManager instances.

        This class method allows you to set a global default market type that will
        be used when no market_type is provided to the create() method.

        Args:
            market_type: Default market type to use

        Examples:
            # Configure FUTURES_USDT as the default market type
            DataSourceManager.configure_defaults(MarketType.FUTURES_USDT)

            # Create a manager using the configured default
            manager = DataSourceManager.create()  # Uses FUTURES_USDT
        """
        cls.DEFAULT_MARKET_TYPE = market_type
        logger.info(f"Configured default market type: {market_type.name}")

    def __init__(
        self,
        market_type: MarketType = MarketType.SPOT,
        provider: DataProvider = DataProvider.BINANCE,
        chart_type: ChartType = ChartType.KLINES,
        rest_client: Optional[RestDataClient] = None,
        cache_dir: Optional[Path] = None,
        use_cache: bool = True,
        max_concurrent: int = 50,
        retry_count: int = 5,
        max_concurrent_downloads: Optional[int] = None,
        vision_client: Optional[VisionDataClient] = None,
        cache_expires_minutes: int = 60,
        use_httpx: bool = False,  # New parameter to choose client type
    ):
        """Initialize the DataSourceManager.

        Args:
            market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN)
            provider: Data provider (BINANCE)
            chart_type: Chart type (KLINES, FUNDING_RATE)
            rest_client: Optional external REST API client
            cache_dir: Directory to store cache files (default: './cache')
            use_cache: Whether to use caching
            max_concurrent: Maximum number of concurrent requests
            retry_count: Number of retries for failed requests
            max_concurrent_downloads: Maximum concurrent downloads for Vision API
            vision_client: Optional external Vision API client
            cache_expires_minutes: Cache expiration time in minutes (default: 60)
            use_httpx: Whether to use httpx instead of curl_cffi for HTTP clients
        """
        # Store initialization settings
        self.market_type = market_type
        self.provider = provider
        self.chart_type = chart_type
        self.max_concurrent = max_concurrent
        self.retry_count = retry_count
        self._use_httpx = use_httpx

        # Handle cache directory configuration
        self._use_cache = use_cache
        if cache_dir is None and use_cache:
            cache_dir = Path("./cache")
            cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache_dir = cache_dir

        # Initialize caching if enabled
        if use_cache and cache_dir:
            self._cache_manager = UnifiedCacheManager(
                cache_dir=cache_dir,
                create_dirs=True,
            )
            # Store these for later use in cache operations
            self._cache_provider = provider
            self._cache_chart_type = chart_type
            self._cache_expiration_minutes = cache_expires_minutes
        else:
            self._cache_manager = None
            self._cache_provider = None
            self._cache_chart_type = None
            self._cache_expiration_minutes = None

        # Client initialization
        self._rest_client = rest_client
        self._rest_client_is_external = rest_client is not None

        self._vision_client = vision_client
        self._vision_client_is_external = vision_client is not None

        self._funding_rate_client = None
        self._funding_rate_client_is_external = False

        self._max_concurrent_downloads = max_concurrent_downloads

        # Register available client implementations
        self._register_client_implementations()

        # Cache statistics
        self._stats = {"hits": 0, "misses": 0, "errors": 0}

        logger.debug(
            f"Initialized DataSourceManager for {market_type.name} using {'httpx' if use_httpx else 'curl_cffi'}"
        )

    def _get_market_type_str(self, market_type: MarketType) -> str:
        """Convert MarketType enum to string representation for Vision API.

        Args:
            market_type: MarketType enum value

        Returns:
            String representation for Vision API
        """
        if market_type.name == MarketType.SPOT.name:
            return "spot"
        elif market_type.name == MarketType.FUTURES_USDT.name:
            return "futures_usdt"
        elif market_type.name == MarketType.FUTURES_COIN.name:
            return "futures_coin"
        elif market_type.name == MarketType.FUTURES.name:
            return "futures_usdt"  # Default to USDT-margined for legacy type
        else:
            raise ValueError(f"Unsupported market type: {market_type}")

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache performance statistics.

        Returns:
            Dictionary containing cache hits, misses, and errors
        """
        return self._stats.copy()

    async def validate_cache_integrity(
        self, symbol: str, interval: str, date: datetime
    ) -> Tuple[bool, Optional[str]]:
        """Validate cache integrity for a specific data point.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            date: Target date

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self._cache_manager:
            return False, "Cache manager not initialized"

        try:
            # Check if cache exists first
            cache_key = self._cache_manager.get_cache_key(
                symbol,
                interval,
                date,
                provider=(
                    self._cache_provider.name if self._cache_provider else "BINANCE"
                ),
                chart_type=(
                    self._cache_chart_type.name if self._cache_chart_type else "KLINES"
                ),
            )
            if cache_key not in self._cache_manager.metadata:
                return False, "Cache miss"

            # Load data and verify format
            df = await self._cache_manager.load_from_cache(
                symbol,
                interval,
                date,
                provider=(
                    self._cache_provider.name if self._cache_provider else "BINANCE"
                ),
                chart_type=(
                    self._cache_chart_type.name if self._cache_chart_type else "KLINES"
                ),
            )
            if df is None:
                return False, "Failed to load cache data"

            # Validate data structure using our centralized validator
            try:
                DataFrameValidator.validate_dataframe(df)
                return True, None
            except ValueError as e:
                return False, str(e)

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def repair_cache(self, symbol: str, interval: str, date: datetime) -> bool:
        """Attempt to repair corrupted cache entry.

        Args:
            symbol: Trading pair symbol
            interval: Time interval
            date: Target date

        Returns:
            True if repair successful, False otherwise
        """
        if not self._cache_manager:
            return False

        try:
            # Invalidate corrupted entry
            self._cache_manager.invalidate_cache(
                symbol,
                interval,
                date,
                provider=(
                    self._cache_provider.name if self._cache_provider else "BINANCE"
                ),
                chart_type=(
                    self._cache_chart_type.name if self._cache_chart_type else "KLINES"
                ),
            )

            # Refetch and cache data
            df = await self._fetch_from_source(
                symbol, date, date + timedelta(days=1), Interval(interval)
            )
            if df.empty:
                return False

            # Validate data before caching
            try:
                DataFrameValidator.validate_dataframe(df)
            except ValueError as e:
                logger.error(f"Cannot repair cache with invalid data: {e}")
                return False

            await self._cache_manager.save_to_cache(
                df,
                symbol,
                interval,
                date,
                provider=(
                    self._cache_provider.name if self._cache_provider else "BINANCE"
                ),
                chart_type=(
                    self._cache_chart_type.name if self._cache_chart_type else "KLINES"
                ),
            )

            # Verify the repair was successful
            is_valid, error = await self.validate_cache_integrity(
                symbol, interval, date
            )
            if not is_valid:
                logger.error(f"Cache repair verification failed: {error}")
                return False

            return True

        except Exception as e:
            logger.error(f"Cache repair failed: {e}")
            return False

    def _estimate_data_points(
        self, start_time: datetime, end_time: datetime, interval: Interval
    ) -> int:
        """Estimate number of data points for a time range.

        Args:
            start_time: Start time
            end_time: End time
            interval: Time interval

        Returns:
            Estimated number of data points
        """
        time_diff = end_time - start_time
        interval_seconds = interval.to_seconds()
        return int(time_diff.total_seconds()) // interval_seconds

    def _should_use_vision_api(
        self, start_time: datetime, end_time: datetime, interval: Interval
    ) -> bool:
        """Determine if Vision API should be used based on time range and interval.

        Args:
            start_time: Start time
            end_time: End time
            interval: Time interval

        Returns:
            True if Vision API should be used, False for REST API
        """
        # Compare enum names rather than objects to avoid issues in parallel testing
        # where enum objects might be different instances due to module reloading

        # Use REST API for small intervals like 1s that Vision doesn't support
        if interval.name == Interval.SECOND_1.name:
            logger.debug("Using REST API for 1s data (Vision API doesn't support it)")
            return False

        # Always use Vision for large time ranges to avoid multiple chunked API calls
        time_range = end_time - start_time
        data_points = self._estimate_data_points(start_time, end_time, interval)

        if data_points > self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS:
            logger.debug(
                f"Using Vision API due to large data request ({data_points} points, "
                f"exceeding REST max of {self.REST_CHUNK_SIZE * self.REST_MAX_CHUNKS})"
            )
            return True

        # Use Vision API for historical data beyond the delay threshold
        # Ensure consistent timezone for comparison
        now = datetime.now(timezone.utc)
        vision_threshold = now - timedelta(hours=self.VISION_DATA_DELAY_HOURS)

        if end_time < vision_threshold:
            logger.debug(
                f"Using Vision API for historical data older than {self.VISION_DATA_DELAY_HOURS} hours"
            )
            return True

        # Default to REST API for recent data
        logger.debug(
            f"Using REST API for recent data within {self.VISION_DATA_DELAY_HOURS} hours"
        )
        return False

    def _format_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Format DataFrame to ensure consistent structure and data types.

        Args:
            df: DataFrame to format

        Returns:
            Formatted DataFrame
        """
        logger.debug(
            f"Formatting DataFrame with shape: {df.shape if not df.empty else 'empty'}"
        )
        logger.debug(
            f"Columns before formatting: {list(df.columns) if not df.empty else 'none'}"
        )
        logger.debug(
            f"Index type before formatting: {type(df.index) if not df.empty else 'none'}"
        )

        # Note: Vision API data no longer needs column name standardization since
        # it now uses KLINE_COLUMNS directly during parsing.
        # However, we still run standardize_column_names for any other potential data sources
        # and to maintain backward compatibility with third-party APIs.
        df = standardize_column_names(df)

        # Then use the centralized formatter
        return DataFrameValidator.format_dataframe(df, self.OUTPUT_DTYPES)

    async def _fetch_from_source(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval: Interval,
        use_vision: bool = False,
    ) -> pd.DataFrame:
        """Fetch data from appropriate source based on parameters.

        Args:
            symbol: Trading pair symbol
            start_time: Start time
            end_time: End time
            interval: Time interval
            use_vision: Whether to try Vision API first (with REST API fallback)

        Returns:
            DataFrame with market data
        """
        # Initialize with empty DataFrame in case of errors
        result_df = self.create_empty_dataframe()

        try:
            # For non-klines chart types, use the appropriate data client
            if self.chart_type != ChartType.KLINES:
                try:
                    client = await self._get_data_client(symbol, interval)

                    # Fetch data using the client with proper timeout handling
                    try:
                        # Use the standard API timeout from config, not arbitrary values
                        result_df = await asyncio.wait_for(
                            client.fetch(start_time, end_time), timeout=MAX_TIMEOUT
                        )
                        # Clean up any lingering force_timeout tasks immediately
                        await self._cleanup_force_timeout_tasks()
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Timeout after {MAX_TIMEOUT}s while fetching data for {symbol}"
                        )
                        # Log timeout event
                        self._log_timeout_with_details(
                            operation=f"Chart data fetch for {symbol}",
                            timeout_value=MAX_TIMEOUT,
                            details={
                                "chart_type": self.chart_type.name,
                                "start_time": start_time.isoformat(),
                                "end_time": end_time.isoformat(),
                            },
                        )
                        return self.create_empty_dataframe()
                except asyncio.TimeoutError:
                    logger.error(f"Timeout while creating data client for {symbol}")
                    return self.create_empty_dataframe()

            # For KLINES, we still use the legacy code path with REST/Vision
            if use_vision:
                try:
                    # Get aligned boundaries once and reuse them
                    vision_start, vision_end = align_time_boundaries(
                        start_time, end_time, interval
                    )

                    logger.info(
                        f"Using Vision API with aligned boundaries: {vision_start} -> {vision_end}"
                    )

                    # Create Vision client if not exists
                    await self._ensure_vision_client(symbol, interval.value)

                    # Fetch from Vision API with aligned boundaries and proper timeout
                    try:
                        # Use the standard API timeout from config, not arbitrary values
                        vision_df = await asyncio.wait_for(
                            self._vision_client.fetch(vision_start, vision_end),
                            timeout=MAX_TIMEOUT,  # Use MAX_TIMEOUT for Vision API
                        )
                        # Clean up any lingering force_timeout tasks immediately
                        await self._cleanup_force_timeout_tasks()
                    except asyncio.TimeoutError:
                        logger.error(
                            f"Vision API timeout after {MAX_TIMEOUT}s, falling back to REST API"
                        )
                        # Log timeout event
                        self._log_timeout_with_details(
                            operation=f"Vision API fetch for {symbol}",
                            timeout_value=MAX_TIMEOUT,
                            details={
                                "interval": interval.value,
                                "start_time": vision_start.isoformat(),
                                "end_time": vision_end.isoformat(),
                            },
                        )
                        use_vision = False  # Fall back to REST API
                    else:
                        # Check if we got valid data
                        if not vision_df.empty:
                            # Filter result to exact requested time range if needed
                            result_df = filter_dataframe_by_time(
                                vision_df, start_time, end_time
                            )

                            # If we have data, return it
                            if not result_df.empty:
                                logger.info(
                                    f"Successfully retrieved {len(result_df)} records from Vision API"
                                )
                                return result_df

                        # If we get here, Vision API failed or returned empty results
                        logger.info(
                            "Vision API returned no data, falling back to REST API"
                        )

                except Exception as e:
                    logger.warning(f"Vision API error, falling back to REST API: {e}")

            # Fall back to REST API (or use it directly if use_vision=False)
            try:
                logger.info(
                    f"Using REST API with original boundaries: {start_time} -> {end_time}"
                )

                # Ensure REST client is initialized
                await self._ensure_rest_client(symbol, interval)

                # Fetch from REST API with proper timeout handling
                try:
                    # Use the standard API timeout from config, not arbitrary values
                    rest_result = await asyncio.wait_for(
                        self._rest_client.fetch(symbol, interval, start_time, end_time),
                        timeout=MAX_TIMEOUT,
                    )
                    # Clean up any lingering force_timeout tasks immediately
                    await self._cleanup_force_timeout_tasks()
                except asyncio.TimeoutError:
                    logger.error(
                        f"REST API timeout after {MAX_TIMEOUT}s while fetching data for {symbol}"
                    )
                    # Log timeout event
                    self._log_timeout_with_details(
                        operation=f"REST API fetch for {symbol}",
                        timeout_value=MAX_TIMEOUT,
                        details={
                            "interval": interval.value,
                            "start_time": start_time.isoformat(),
                            "end_time": end_time.isoformat(),
                        },
                    )
                    return self.create_empty_dataframe()

                # Unpack the tuple - RestDataClient.fetch returns (df, stats)
                rest_df, stats = rest_result

                if not rest_df.empty:
                    logger.info(
                        f"Successfully retrieved {len(rest_df)} records from REST API"
                    )
                    # Validate the DataFrame
                    DataFrameValidator.validate_dataframe(rest_df)
                    return rest_df

                logger.debug(
                    f"REST API returned no data for {symbol} from {start_time} to {end_time}"
                )

            except Exception as e:
                logger.error(f"REST API fetch error: {e}")

        except Exception as e:
            logger.error(f"Error fetching data: {e}")

        # If we reach here, all sources failed or returned empty results
        logger.info(
            f"No data returned for {symbol} from {start_time} to {end_time} from any source"
        )
        return self.create_empty_dataframe()

    def _get_aligned_cache_date(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: Interval,
        use_vision: bool,
    ) -> datetime:
        """Get aligned date for cache operations that's consistent across REST and Vision APIs.

        Args:
            start_time: Original start time
            end_time: Original end time
            interval: Time interval
            use_vision: Whether Vision API is being used

        Returns:
            Aligned date for cache operations
        """
        if use_vision:
            # For Vision API, get aligned start time
            aligned_start, _ = align_time_boundaries(start_time, end_time, interval)
            return aligned_start
        else:
            # For REST API, use original start time - the REST client will handle alignment
            return start_time

    async def get_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval: Interval = Interval.SECOND_1,
        use_cache: bool = True,
        enforce_source: DataSource = DataSource.AUTO,
        provider: Optional[DataProvider] = None,
        chart_type: Optional[ChartType] = None,
    ) -> pd.DataFrame:
        """Get data for symbol within time range, with smart source selection.

        Args:
            symbol: Trading pair symbol (e.g. "BTCUSDT")
            start_time: Start time (must be timezone-aware, preferably UTC)
            end_time: End time (must be timezone-aware, preferably UTC)
            interval: Time interval (e.g. MINUTE_1, HOUR_1). See Interval enum.
            use_cache: Whether to use cache for this specific query
            enforce_source: Force specific data source (AUTO, REST, VISION)
            provider: Optional override for data provider (default: use the manager's provider)
            chart_type: Optional override for chart type (default: use the manager's chart type)

        Returns:
            DataFrame with market data in standardized format

        Raises:
            ValueError: If time boundaries are invalid (e.g., future dates)

        Examples:
            # Basic usage with defaults
            df = await manager.get_data("BTCUSDT", start_time, end_time)

            # Specify interval and force REST API
            df = await manager.get_data(
                "ETHUSDT",
                start_time,
                end_time,
                interval=Interval.MINUTE_15,
                enforce_source=DataSource.REST
            )

            # Request different chart type from same manager instance
            funding_df = await manager.get_data(
                "BTCUSDT",
                start_time,
                end_time,
                interval=Interval.HOUR_8,
                chart_type=ChartType.FUNDING_RATE
            )
        """
        try:
            # Call the implementation directly without a global timeout
            # Individual operations inside will have their own timeouts
            df = await self._get_data_impl(
                symbol,
                start_time,
                end_time,
                interval,
                use_cache,
                enforce_source,
                provider,
                chart_type,
            )

            # Proactively clean up any lingering force_timeout tasks after operation completes
            await self._cleanup_force_timeout_tasks()

            return df
        except asyncio.TimeoutError:
            self._log_timeout_with_details(
                operation=f"get_data operation for {symbol}",
                timeout_value=MAX_TIMEOUT,
                details={
                    "interval": interval.value,
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat(),
                    "enforce_source": enforce_source.name,
                },
            )
            # Return empty DataFrame on timeout
            return self.create_empty_dataframe()
        except Exception as e:
            logger.error(f"Error in get_data for {symbol}: {e}")
            # Return empty DataFrame on any error
            return self.create_empty_dataframe()

    async def _get_data_impl(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval: Interval = Interval.SECOND_1,
        use_cache: bool = True,
        enforce_source: DataSource = DataSource.AUTO,
        provider: Optional[DataProvider] = None,
        chart_type: Optional[ChartType] = None,
    ) -> pd.DataFrame:
        """Implementation of get_data with all the logic but without the timeout wrapper.

        This contains the original get_data implementation to avoid nesting timeouts.
        """
        # Override provider and chart_type if specified
        original_provider = self.provider
        original_chart_type = self.chart_type

        if provider is not None:
            self.provider = provider

        if chart_type is not None:
            self.chart_type = chart_type

        try:
            # Standardize input parameters
            symbol = symbol.upper()

            # Apply comprehensive time boundary validation
            start_time, end_time, metadata = (
                DataValidation.validate_query_time_boundaries(
                    start_time, end_time, handle_future_dates="error", interval=interval
                )
            )

            # Log existing warnings from validation except data availability
            data_availability_message = metadata.get("data_availability_message", "")
            for warning in metadata.get("warnings", []):
                # Only log warnings that aren't about data availability
                logger.warning(warning)

            # Log input parameters
            logger.info(
                f"Getting {self.chart_type.value} data for {symbol} from {start_time} to {end_time} "
                f"with interval {interval.value}, provider={self.provider.name}"
            )

            # Store data availability info for later use if fetch fails
            is_data_likely_available = metadata.get("data_likely_available", True)

            # Determine data source to use (only applies to KLINES)
            use_vision = self._determine_data_source(
                start_time, end_time, interval, enforce_source
            )

            # Check if we can use cache
            is_valid = use_cache and self._cache_manager
            is_cache_hit = False

            # Cache key components
            cache_components = {
                "symbol": symbol,
                "interval": interval.value,
                "provider": self.provider.name,
                "chart_type": self.chart_type.name,
            }

            try:
                # Attempt to load from cache if enabled
                if is_valid:
                    # Get the aligned cache date
                    cache_date = self._get_aligned_cache_date(
                        start_time, end_time, interval, use_vision
                    )

                    cached_data = await self._cache_manager.load_from_cache(
                        date=cache_date,
                        **{
                            "symbol": symbol,
                            "interval": interval.value,
                            "provider": (
                                provider.name
                                if provider
                                else (
                                    self._cache_provider.name
                                    if self._cache_provider
                                    else "BINANCE"
                                )
                            ),
                            "chart_type": (
                                chart_type.name
                                if chart_type
                                else (
                                    self._cache_chart_type.name
                                    if self._cache_chart_type
                                    else "KLINES"
                                )
                            ),
                        },
                    )

                    if cached_data is not None:
                        # Filter DataFrame based on original requested time range
                        # Use inclusive start, inclusive end consistent with API behavior
                        filtered_data = filter_dataframe_by_time(
                            cached_data, start_time, end_time
                        )

                        if not filtered_data.empty:
                            self._stats["hits"] += 1
                            logger.info(
                                f"Cache hit for {symbol} {self.chart_type.name} from {start_time}"
                            )
                            return filtered_data

                        logger.info(
                            "Cache hit, but filtered data is empty. Fetching from source."
                        )
                    else:
                        logger.info(
                            f"Cache miss for {symbol} {self.chart_type.name} from {start_time}"
                        )

                    self._stats["misses"] += 1

            except Exception as e:
                logger.error(f"Cache error: {e}")
                self._stats["errors"] += 1
                # Continue with fetching from source

            # Fetch data from appropriate source
            df = await self._fetch_from_source(
                symbol, start_time, end_time, interval, use_vision
            )

            # If data is partially retrieved or empty and we have a data availability warning, log it now
            if not is_data_likely_available:
                # Calculate expected records more precisely based on interval
                time_diff = (end_time - start_time).total_seconds()
                interval_seconds = interval.to_seconds()
                expected_records = max(1, int(time_diff / interval_seconds))
                actual_records = len(df)

                # Calculate the shortage and percentage
                records_shortage = expected_records - actual_records
                completion_pct = (
                    (actual_records / expected_records * 100)
                    if expected_records > 0
                    else 0
                )

                # Only show warning if we're actually missing records
                if records_shortage > 0:
                    # Get time range information if available
                    time_range_info = ""
                    if "time_range" in metadata:
                        tr = metadata["time_range"]
                        start_time_str = tr.get("start_time", "unknown")
                        end_time_str = tr.get("end_time", "unknown")
                        span_seconds = tr.get("time_span_seconds", 0)
                        time_range_info = f" [Range: {start_time_str} -> {end_time_str}, span: {span_seconds:.1f}s]"

                    logger.warning(
                        f"{data_availability_message} Retrieved {actual_records}/{expected_records} records "
                        f"({completion_pct:.1f}% complete, missing {records_shortage} records) "
                        f"for symbol {symbol} with interval {interval.value}{time_range_info}"
                    )

                    # If no data was retrieved and this is likely due to very recent data not being consolidated
                    if actual_records == 0 and "time_range" in metadata:
                        # Try to fetch with truncated end time (1 minute in the past as a safe buffer)
                        current_time = datetime.now(timezone.utc)
                        safe_end_time = current_time - timedelta(minutes=1)

                        # Only proceed if our query includes some time that's not extremely recent
                        if start_time < safe_end_time:
                            logger.info(
                                f"Attempting to retrieve historical data up to {safe_end_time.isoformat()} "
                                f"for {symbol} with interval {interval.value}"
                            )

                            try:
                                # Try to fetch data up to the safe time boundary
                                historical_df = await self._fetch_from_source(
                                    symbol,
                                    start_time,
                                    safe_end_time,
                                    interval,
                                    use_vision,
                                )

                                if not historical_df.empty:
                                    logger.info(
                                        f"Successfully retrieved {len(historical_df)} historical records for {symbol} "
                                        f"(from {start_time} to {safe_end_time})"
                                    )
                                    df = historical_df
                            except Exception as e:
                                logger.error(
                                    f"Failed to retrieve historical data: {str(e)}"
                                )

            # Cache if enabled and data is not empty
            if is_valid and not df.empty and self._cache_manager:
                try:
                    # Get the aligned cache date
                    cache_date = self._get_aligned_cache_date(
                        start_time, end_time, interval, use_vision
                    )

                    await self._cache_manager.save_to_cache(
                        df=df,
                        date=cache_date,
                        symbol=symbol,
                        interval=interval.value,
                        provider=(
                            provider.name
                            if provider
                            else (
                                self._cache_provider.name
                                if self._cache_provider
                                else "BINANCE"
                            )
                        ),
                        chart_type=(
                            chart_type.name
                            if chart_type
                            else (
                                self._cache_chart_type.name
                                if self._cache_chart_type
                                else "KLINES"
                            )
                        ),
                    )
                    logger.info(
                        f"Cached {len(df)} records for {symbol} {self.chart_type.name}"
                    )
                except Exception as e:
                    logger.error(f"Error caching data: {e}")

            return df

        finally:
            # Restore original values
            self.provider = original_provider
            self.chart_type = original_chart_type

    def _determine_data_source(
        self,
        start_time: datetime,
        end_time: datetime,
        interval: Interval,
        enforce_source: DataSource,
    ) -> bool:
        """Determine which data source to use based on parameters and preferences.

        Args:
            start_time: Start time
            end_time: End time
            interval: Time interval
            enforce_source: User-enforced data source preference

        Returns:
            True if Vision API should be used, False for REST API
        """
        # Handle user-enforced source selection
        if enforce_source == DataSource.VISION:
            logger.info("Using Vision API (enforced)")
            return True
        elif enforce_source == DataSource.REST:
            logger.info("Using REST API (enforced)")
            return False

        # AUTO: Apply smart selection logic
        use_vision = self._should_use_vision_api(start_time, end_time, interval)
        logger.info(
            f"Auto-selected source: {'Vision API' if use_vision else 'REST API'}"
        )
        return use_vision

    async def __aenter__(self):
        """Initialize resources when entering the context."""
        logger.debug(f"Initializing DataSourceManager for {self.market_type.name}")

        # Proactively clean up any force_timeout tasks that might cause hanging
        await self._cleanup_force_timeout_tasks()

        # Register available client implementations
        self._register_client_implementations()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting the context."""
        logger.debug("DataSourceManager starting __aexit__ cleanup")

        # Pre-emptively break circular references that might cause hanging
        if hasattr(self, "_rest_client") and self._rest_client:
            client = self._rest_client
            if hasattr(client, "_client") and client._client:
                if hasattr(client._client, "_curlm") and client._client._curlm:
                    logger.debug(
                        "Pre-emptively cleaning _curlm reference in _rest_client"
                    )
                    client._client._curlm = None

        if hasattr(self, "_vision_client") and self._vision_client:
            client = self._vision_client
            if hasattr(client, "_client") and client._client:
                if hasattr(client._client, "_curlm") and client._client._curlm:
                    logger.debug(
                        "Pre-emptively cleaning _curlm reference in _vision_client"
                    )
                    client._client._curlm = None

        # Initialize _funding_rate_client_is_external if it doesn't exist
        if not hasattr(self, "_funding_rate_client_is_external"):
            logger.debug(
                "Initializing missing _funding_rate_client_is_external attribute"
            )
            self._funding_rate_client_is_external = True

        # List of clients to clean up - only include attributes that actually exist
        clients_to_cleanup = []

        if hasattr(self, "_rest_client"):
            clients_to_cleanup.append(
                (
                    "_rest_client",
                    "REST client",
                    getattr(self, "_rest_client_is_external", True),
                )
            )

        if hasattr(self, "_vision_client"):
            clients_to_cleanup.append(
                (
                    "_vision_client",
                    "Vision client",
                    getattr(self, "_vision_client_is_external", True),
                )
            )

        if hasattr(self, "_cache_manager"):
            clients_to_cleanup.append(("_cache_manager", "cache manager", False))

        if hasattr(self, "_funding_rate_client"):
            clients_to_cleanup.append(
                (
                    "_funding_rate_client",
                    "funding rate client",
                    self._funding_rate_client_is_external,
                )
            )

        # Use direct resource cleanup pattern for consistent handling of resources
        await direct_resource_cleanup(self, *clients_to_cleanup)

        logger.debug("DataSourceManager completed __aexit__ cleanup")

    async def _cleanup_force_timeout_tasks(self):
        """Find and clean up any _force_timeout tasks that might cause hanging.

        This is a proactive approach to prevent hanging issues caused by
        lingering force_timeout tasks in curl_cffi AsyncCurl objects.
        """
        # Find all tasks that might be related to _force_timeout
        force_timeout_tasks = []

        # Get all tasks
        all_tasks = asyncio.all_tasks()

        # First identify curl_cffi force_timeout tasks specifically
        for task in all_tasks:
            task_str = str(task)
            # Only target actual force_timeout tasks
            if "_force_timeout" in task_str and not task.done():
                # Check if it's been running for more than 5 seconds
                if hasattr(task, "_coro") and hasattr(task._coro, "cr_frame"):
                    force_timeout_tasks.append(task)

        # If we have too many tasks, be more selective
        if len(force_timeout_tasks) > 20:
            logger.warning(
                f"Found {len(force_timeout_tasks)} timeout tasks, filtering to avoid excessive cancellation"
            )
            # Keep only the tasks that are most likely to be leaked
            filtered_tasks = []
            for task in force_timeout_tasks:
                task_str = str(task)
                # More selective criteria
                if "_force_timeout" in task_str and "AsyncCurl" in task_str:
                    filtered_tasks.append(task)
            force_timeout_tasks = filtered_tasks

        # Now check for other curl_cffi tasks but only if they look stuck
        # and are not part of active data retrieval operations
        if len(force_timeout_tasks) < 10:  # Only if we don't already have too many
            for task in all_tasks:
                if task in force_timeout_tasks:
                    continue  # Skip tasks we've already selected

                task_str = str(task)
                # Look for specific curl_cffi tasks that might be lingering
                if (
                    "curl_cffi" in task_str
                    and "AsyncSession.request" in task_str
                    and not task.done()
                    and "_fetch_klines_chunk"
                    not in task_str  # Don't cancel active data retrieval
                    and "_fetch_chunk_with_semaphore"
                    not in task_str  # Don't cancel active data retrieval
                ):
                    force_timeout_tasks.append(task)

        if force_timeout_tasks:
            # Limit the number of tasks we cancel to a reasonable amount
            if len(force_timeout_tasks) > 20:
                logger.warning(
                    f"Limiting task cancellation to 20 tasks (out of {len(force_timeout_tasks)} found)"
                )
                force_timeout_tasks = force_timeout_tasks[:20]

            logger.warning(
                f"Proactively cancelling {len(force_timeout_tasks)} timeout/curl_cffi tasks"
            )
            # Cancel all force_timeout tasks
            for task in force_timeout_tasks:
                task.cancel()

            # Wait for cancellation to complete with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*force_timeout_tasks, return_exceptions=True),
                    timeout=0.5,  # Short timeout to avoid blocking
                )
                logger.debug(
                    f"Successfully cancelled {len(force_timeout_tasks)} timeout/curl_cffi tasks"
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timeout waiting for curl_cffi tasks to cancel, proceeding anyway"
                )

            # Check if tasks were actually cancelled
            still_running = [t for t in force_timeout_tasks if not t.done()]
            if still_running:
                logger.warning(
                    f"{len(still_running)} curl_cffi tasks still running after cancel attempt"
                )
                for task in still_running:
                    # Extra cancellation attempt
                    task.cancel()

        return len(force_timeout_tasks)

    async def _ensure_rest_client(self, symbol: str, interval: Interval) -> None:
        """Ensure REST client is initialized.

        Args:
            symbol: Trading symbol
            interval: Time interval
        """
        try:
            if self._rest_client is None:
                logger.debug(f"Creating new REST client for {symbol} {interval.value}")
                # Apply timeout to client creation
                self._rest_client = await asyncio.wait_for(
                    asyncio.to_thread(
                        RestDataClient,
                        market_type=self.market_type,
                        max_concurrent=self.max_concurrent,
                        retry_count=self.retry_count,
                    ),
                    timeout=MAX_TIMEOUT,
                )
                self._rest_client_is_external = False
        except asyncio.TimeoutError:
            self._log_timeout_with_details(
                operation=f"RestDataClient initialization for {symbol}",
                timeout_value=MAX_TIMEOUT,
                details={
                    "interval": interval.value,
                    "market_type": self.market_type.name,
                },
            )
            raise

    async def _ensure_vision_client(self, symbol: str, interval: str) -> None:
        """Ensure Vision API client is initialized.

        Args:
            symbol: Trading symbol
            interval: Time interval as string
        """
        try:
            if self._vision_client is None:
                # For Vision API, use string interval format
                logger.debug(f"Creating new Vision client for {symbol} {interval}")

                # Convert MarketType to string for the VisionDataClient
                if isinstance(self.market_type, MarketType):
                    market_type_str = self.market_type.name.lower()
                else:
                    market_type_str = str(self.market_type).lower()

                # Apply timeout to client creation
                self._vision_client = await asyncio.wait_for(
                    asyncio.to_thread(
                        VisionDataClient,
                        symbol=symbol,
                        interval=interval,
                        market_type=market_type_str,
                        max_concurrent_downloads=self._max_concurrent_downloads,
                    ),
                    timeout=MAX_TIMEOUT,
                )
                self._vision_client_is_external = False
        except asyncio.TimeoutError:
            self._log_timeout_with_details(
                operation=f"VisionDataClient initialization for {symbol}",
                timeout_value=MAX_TIMEOUT,
                details={"interval": interval, "market_type": market_type_str},
            )
            raise

    def _register_client_implementations(self):
        """Register all client implementations with the factory."""
        try:
            # Register BinanceFundingRateClient for funding rate data
            DataClientFactory.register_client(
                provider=DataProvider.BINANCE,
                market_type=MarketType.FUTURES_USDT,
                chart_type=ChartType.FUNDING_RATE,
                client_class=BinanceFundingRateClient,
            )

            DataClientFactory.register_client(
                provider=DataProvider.BINANCE,
                market_type=MarketType.FUTURES_COIN,
                chart_type=ChartType.FUNDING_RATE,
                client_class=BinanceFundingRateClient,
            )

            logger.debug("Registered client implementations with factory")
        except Exception as e:
            logger.error(f"Failed to register client implementations: {e}")

    async def _get_data_client(
        self, symbol: str, interval: Interval
    ) -> DataClientInterface:
        """Get the appropriate data client for the configured parameters.

        This method is part of the transition to the new architecture. It will create
        a client from the factory if the chart type is supported, or fall back to the
        legacy clients for backward compatibility.

        Args:
            symbol: Trading pair symbol
            interval: Time interval

        Returns:
            DataClientInterface implementation
        """
        try:
            # Apply timeout to the entire client creation process
            return await asyncio.wait_for(
                self._get_data_client_impl(symbol, interval), timeout=MAX_TIMEOUT
            )
        except asyncio.TimeoutError:
            self._log_timeout_with_details(
                operation=f"Data client creation for {symbol}",
                timeout_value=MAX_TIMEOUT,
                details={
                    "interval": interval.value,
                    "chart_type": self.chart_type.name,
                    "market_type": self.market_type.name,
                },
            )
            # Re-raise to allow caller to handle
            raise

    async def _get_data_client_impl(
        self, symbol: str, interval: Interval
    ) -> DataClientInterface:
        """Implementation of _get_data_client without timeout wrapper.

        This contains the original implementation to avoid nesting timeouts.
        """
        # Try to get a client from the factory for non-klines data
        if self.chart_type != ChartType.KLINES:
            try:
                if (
                    not self._rest_client_is_external
                    or (
                        hasattr(self._rest_client, "symbol")
                        and self._rest_client.symbol != symbol
                    )
                    or (
                        hasattr(self._rest_client, "interval")
                        and self._rest_client.interval != interval
                    )
                ):
                    # Create a new client
                    self._rest_client = RestDataClient(
                        market_type=self.market_type,
                        max_concurrent=self.max_concurrent,
                        retry_count=self.retry_count,
                    )
                    self._rest_client_is_external = False

                return self._rest_client
            except Exception as e:
                logger.error(f"Failed to create data client from factory: {e}")
                # Fall back to legacy clients

        # For KLINES, we still use the legacy clients
        # Initialize REST client if needed
        if not self._rest_client:
            self._rest_client = RestDataClient(
                market_type=self.market_type,
                max_concurrent=self.max_concurrent,
                retry_count=self.retry_count,
            )

        return self._rest_client

    def create_empty_dataframe(self) -> pd.DataFrame:
        """Create an empty DataFrame with the correct structure for the configured chart type.

        Returns:
            Empty DataFrame with correct columns and types
        """
        if self.chart_type == ChartType.FUNDING_RATE:
            return create_empty_funding_rate_dataframe()
        return create_empty_dataframe()

    async def query_data(self, query_config: DataQueryConfig) -> pd.DataFrame:
        """Query data using a DataQueryConfig for improved parameter organization.

        This method provides a more Pythonic interface by using a configuration object
        to organize all the query parameters.

        Args:
            query_config: Configuration object containing all query parameters

        Returns:
            DataFrame with market data in standardized format

        Examples:
            # Create query config and fetch data
            query = DataQueryConfig.create(
                "BTCUSDT",
                start_time,
                end_time,
                interval=Interval.HOUR_1,
                enforce_source=DataSource.VISION
            )
            df = await manager.query_data(query)
        """
        return await self.get_data(
            symbol=query_config.symbol,
            start_time=query_config.start_time,
            end_time=query_config.end_time,
            interval=query_config.interval,
            use_cache=query_config.use_cache,
            enforce_source=query_config.enforce_source,
            provider=query_config.provider,
            chart_type=query_config.chart_type,
        )

    def _log_timeout_with_details(
        self,
        operation: str,
        timeout_value: float,
        details: dict = None,
        stack_level: int = 1,
    ) -> None:
        """Enhanced timeout logging with diagnostic details.

        This method adds file name, line number, call stack and detailed diagnostic
        information to timeout logs for easier troubleshooting.

        Args:
            operation: Description of the operation that timed out
            timeout_value: The timeout value in seconds
            details: Additional context about the operation
            stack_level: How many frames to go back in the stack trace (default: 1)
        """
        if details is None:
            details = {}

        # Get caller information
        frame = inspect.currentframe()
        # Navigate up the stack to find the caller
        for _ in range(stack_level):
            if frame.f_back is not None:
                frame = frame.f_back

        # Extract file name and line number
        file_name = frame.f_code.co_filename
        line_no = frame.f_lineno
        function_name = frame.f_code.co_name

        # Get a summarized stack trace (limit to 3 frames to avoid clutter)
        stack_summary = []
        for frame_info in traceback.extract_stack()[-4:-1]:  # Skip the current frame
            stack_summary.append(
                f"{frame_info.filename}:{frame_info.lineno} in {frame_info.name}"
            )

        # Add diagnostic information to details
        diagnostic_details = {
            **details,
            "file": os.path.basename(file_name),
            "line": line_no,
            "function": function_name,
            "stack_trace": " -> ".join(stack_summary),
        }

        # Log the timeout with enhanced details
        logger.log_timeout(
            operation=operation, timeout_value=timeout_value, details=diagnostic_details
        )

    def _validate_time_range(self, symbol, start_time, end_time, interval):
        """Validate the time range and check for potential issues.

        Args:
            symbol: Trading pair symbol
            start_time: Start time for data retrieval
            end_time: End time for data retrieval
            interval: Time interval
        """
        # Check if date range includes future or very recent dates
        current_time = datetime.now(timezone.utc)

        # Calculate the complete bar threshold - a completed bar has passed its full interval time
        interval_seconds = interval.to_seconds()
        safe_buffer = timedelta(seconds=interval_seconds * 2)  # Two intervals as buffer

        if end_time > current_time - safe_buffer:
            # Change from warning to info since this is expected behavior, not an error condition
            logger.info(
                f"Data for end time ({end_time.isoformat()}) may not be fully consolidated yet"
            )
