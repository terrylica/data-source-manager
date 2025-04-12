#!/usr/bin/env python
r"""VisionDataClient provides direct access to Binance Vision API for historical data.

This module implements a client for retrieving historical market data from the
Binance Vision API. It provides functions for fetching, validating, and processing data.

Functionality:
- Fetch historical market data by symbol, interval, and time range
- Validate data integrity and structure
- Process data into pandas DataFrames for analysis

The VisionDataClient is primarily used through the DataSourceManager, which provides
a unified interface for data retrieval with automatic source selection and caching.

For most use cases, users should interact with the DataSourceManager rather than
directly with this client.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence, TypeVar, Generic, Union, List, Dict, Any, Tuple
import os
import tempfile
import zipfile
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
import re

import pandas as pd

from utils.logger_setup import logger
from utils.market_constraints import Interval, MarketType
from utils.time_utils import (
    filter_dataframe_by_time,
)
from utils.config import (
    standardize_column_names,
    KLINE_COLUMNS,
    MAXIMUM_CONCURRENT_DOWNLOADS,
)
from core.sync.vision_constraints import (
    TimestampedDataFrame,
    FileType,
    get_vision_url,
    detect_timestamp_unit,
    MICROSECOND_DIGITS,
)

# Define the type variable for VisionDataClient
T = TypeVar("T")


class VisionDataClient(Generic[T]):
    """Vision Data Client for direct access to Binance historical data."""

    def __init__(
        self,
        symbol: str,
        interval: str = "1s",
        market_type: Union[str, MarketType] = MarketType.SPOT,
    ):
        """Initialize Vision Data Client.

        Args:
            symbol: Trading symbol e.g. 'BTCUSDT'
            interval: Kline interval e.g. '1s', '1m'
            market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN) or string
        """
        self.symbol = symbol.upper()
        self.interval = interval
        self.market_type = market_type

        # Convert MarketType enum to string if needed
        market_type_str = market_type
        if isinstance(market_type, MarketType):
            try:
                market_name = market_type.name
                if market_name == "SPOT":
                    market_type_str = "spot"
                elif market_name == "FUTURES_USDT":
                    market_type_str = "futures_usdt"
                elif market_name == "FUTURES_COIN":
                    market_type_str = "futures_coin"
                elif market_name == "FUTURES":
                    market_type_str = "futures_usdt"  # Default to USDT for legacy type
                else:
                    raise ValueError(f"Unsupported market type: {market_type}")
            except (AttributeError, TypeError):
                # Fallback to string representation for safer comparison
                market_str = str(market_type).upper()
                if "SPOT" in market_str:
                    market_type_str = "spot"
                elif "FUTURES_USDT" in market_str or "FUTURES" == market_str:
                    market_type_str = "futures_usdt"
                elif "FUTURES_COIN" in market_str:
                    market_type_str = "futures_coin"
                else:
                    raise ValueError(f"Unsupported market type: {market_type}")

        self.market_type_str = market_type_str

        # Parse interval string to Interval object
        try:
            # Try to find the interval enum by value
            self.interval_obj = next((i for i in Interval if i.value == interval), None)
            if self.interval_obj is None:
                # Try by enum name (upper case with _ instead of number)
                try:
                    self.interval_obj = Interval[interval.upper()]
                except KeyError:
                    raise ValueError(f"Invalid interval: {interval}")
        except Exception as e:
            logger.warning(
                f"Could not parse interval {interval}, using SECOND_1 as default: {e}"
            )
            self.interval_obj = Interval.SECOND_1

        # Create httpx client instead of requests Session
        self._client = httpx.Client(
            timeout=30.0,  # Increased timeout for better reliability
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json, application/zip",
            },
            follow_redirects=True,  # Automatically follow redirects
        )

    def __enter__(self) -> "VisionDataClient":
        """Context manager entry."""
        return self

    def __exit__(self, _exc_type, _exc_val, _exc_tb):
        """Context manager exit."""
        # Release resources
        if hasattr(self, "_client") and self._client:
            if hasattr(self._client, "close") and callable(self._client.close):
                self._client.close()

    @staticmethod
    def _create_empty_dataframe() -> TimestampedDataFrame:
        """Create an empty dataframe with the correct structure.

        Returns:
            Empty TimestampedDataFrame with the correct columns
        """
        # Use the standardized empty dataframe function from config
        from utils.config import create_empty_dataframe

        # Create empty dataframe and convert to TimestampedDataFrame format
        df = create_empty_dataframe()

        # Set index to open_time_us (required by TimestampedDataFrame)
        if "open_time_us" not in df.columns:
            df["open_time_us"] = pd.Series(dtype="int64")
            df = df.set_index("open_time_us")

        return TimestampedDataFrame(df)

    def _get_interval_seconds(self, interval: str) -> int:
        """Get interval duration in seconds from interval string.

        This method handles converting string intervals directly to seconds
        without requiring the MarketInterval enum object.

        Args:
            interval: Interval string (e.g., "1s", "1m", "1h")

        Returns:
            Number of seconds in the interval
        """
        # Parse interval value and unit
        match = re.match(r"(\d+)([smhdwM])", interval)
        if not match:
            raise ValueError(f"Invalid interval format: {interval}")

        num, unit = match.groups()
        num = int(num)

        # Define multipliers for each unit
        multipliers = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800,
            "M": 2592000,  # Approximate - using 30 days
        }

        if unit not in multipliers:
            raise ValueError(f"Unknown interval unit: {unit}")

        return num * multipliers[unit]

    def _validate_timestamp_safety(self, date: datetime) -> bool:
        """Check if a given timestamp is safe to use with pandas datetime conversion.

        Args:
            date: The datetime to check

        Returns:
            True if the timestamp is safe, False if it might cause out-of-bounds errors

        Note:
            Pandas can have issues with timestamps very far in the future due to
            nanosecond conversion limitations. This check helps prevent those issues.
        """
        try:
            # Check if date is within pandas timestamp limits
            # The max timestamp supported is approximately year 2262
            max_safe_year = 2262
            if date.year > max_safe_year:
                logger.warning(
                    f"Date {date.isoformat()} exceeds pandas timestamp safe year limit ({max_safe_year})"
                )
                return False

            # Test conversion to pandas timestamp to see if it would raise an error
            _ = pd.Timestamp(date)
            return True
        except (OverflowError, ValueError, pd.errors.OutOfBoundsDatetime) as e:
            logger.warning(
                f"Date {date.isoformat()} caused timestamp validation error: {e}"
            )
            return False

    def _process_timestamp_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process timestamp columns in the dataframe, handling various formats.

        Args:
            df: DataFrame with timestamp columns to process

        Returns:
            DataFrame with processed timestamp columns
        """
        if df.empty:
            return df

        try:
            # Check timestamp format if dataframe has rows
            if len(df) > 0:
                first_ts = df.iloc[0, 0]  # First timestamp in first column

                try:
                    # Detect timestamp unit using the standardized function
                    timestamp_unit = detect_timestamp_unit(first_ts)

                    # Log the first and last timestamps for debugging
                    logger.debug(f"First timestamp: {first_ts} ({timestamp_unit})")
                    if len(df) > 1:
                        last_ts = df.iloc[-1, 0]
                        logger.debug(f"Last timestamp: {last_ts} ({timestamp_unit})")

                    # Convert timestamps to datetime using the detected unit
                    if "open_time" in df.columns:
                        df["open_time"] = pd.to_datetime(
                            df["open_time"], unit=timestamp_unit, utc=True
                        )
                    if "close_time" in df.columns:
                        df["close_time"] = pd.to_datetime(
                            df["close_time"], unit=timestamp_unit, utc=True
                        )

                    logger.debug(
                        f"Converted timestamps to datetime using {timestamp_unit} unit"
                    )

                except ValueError as e:
                    logger.warning(f"Error detecting timestamp unit: {e}")
                    # Fall back to default handling with microseconds as unit
                    if "open_time" in df.columns:
                        df["open_time"] = pd.to_datetime(
                            df["open_time"], unit="us", utc=True
                        )
                    if "close_time" in df.columns:
                        df["close_time"] = pd.to_datetime(
                            df["close_time"], unit="us", utc=True
                        )

        except Exception as e:
            logger.error(f"Error processing timestamp columns: {e}")

        return df

    def _download_file(self, date: datetime) -> Optional[pd.DataFrame]:
        """Download and process data file for a specific date.

        Args:
            date: Date to download

        Returns:
            DataFrame with data or None if download failed
        """
        try:
            # First check if the date is safe to process with pandas
            if not self._validate_timestamp_safety(date):
                logger.error(
                    f"Skipping date {date.date()} due to potential timestamp overflow"
                )
                return None

            # Generate URL for the data - ensure we use interval string value
            interval_str = self.interval

            # Debug for interval
            logger.debug(
                f"Self.interval is {self.interval} of type {type(self.interval)}"
            )
            logger.debug(
                f"Self.interval_obj is {self.interval_obj} of type {type(self.interval_obj)}"
            )

            # Check if interval is an enum object with a value attribute
            if hasattr(self.interval_obj, "value"):
                interval_str = self.interval_obj.value
                logger.debug(f"Using interval string value: {interval_str}")
            else:
                logger.debug(
                    f"interval_obj does not have 'value' attribute, using {interval_str}"
                )

            url = get_vision_url(
                symbol=self.symbol,
                interval=interval_str,  # Use string value
                date=date,
                file_type=FileType.DATA,  # Explicitly pass proper FileType.DATA enum
                market_type=self.market_type_str,
            )

            logger.debug(f"Downloading data from {url}")

            # Download the file using httpx client
            try:
                # Make request using httpx
                response = self._client.get(url)

                # Check response status
                if response.status_code != 200:
                    # Calculate days difference between date and now
                    now = datetime.now(timezone.utc)
                    days_difference = (now.date() - date.date()).days

                    # For 404 (Not Found) status, check if it's within 2 days of now
                    if response.status_code == 404 and days_difference <= 2:
                        # We expect recent data might not be available yet, so just show a warning
                        logger.warning(
                            f"Recent data not yet available from Vision API: {date.date()} (HTTP 404)"
                        )
                    else:
                        # For data that should be available or other error codes, log as error
                        logger.error(
                            f"Failed to download data: HTTP {response.status_code}"
                        )
                    return None

                # Get response content
                content = response.content
                logger.debug(
                    f"Successfully downloaded {url} - size: {len(content)} bytes"
                )

            except httpx.RequestError as e:
                # Calculate days difference between date and now for request errors too
                now = datetime.now(timezone.utc)
                days_difference = (now.date() - date.date()).days

                if days_difference <= 2:
                    logger.warning(
                        f"Error downloading recent data for {date.date()}: {e}"
                    )
                else:
                    logger.error(f"Error downloading data for {date.date()}: {e}")
                return None

            # Create a temporary file to store the zip
            with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name

            try:
                # Extract the zip file
                with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
                    # Get the CSV file name (should be the only file in the zip)
                    file_list = zip_ref.namelist()
                    if not file_list:
                        logger.error("Zip file is empty")
                        return None

                    csv_file = file_list[0]
                    logger.debug(f"Found CSV file in zip: {csv_file}")

                    # Extract to a temporary directory
                    with tempfile.TemporaryDirectory() as temp_dir:
                        zip_ref.extract(csv_file, temp_dir)
                        csv_path = os.path.join(temp_dir, csv_file)

                        # Read the CSV file
                        df = pd.read_csv(csv_path)
                        logger.debug(f"Read {len(df)} rows from CSV")

                        # Process the data
                        if not df.empty:
                            # If number of columns match, use the standard names
                            if len(df.columns) == len(KLINE_COLUMNS):
                                df.columns = KLINE_COLUMNS
                            else:
                                logger.warning(
                                    f"Column count mismatch: expected {len(KLINE_COLUMNS)}, got {len(df.columns)}"
                                )

                            # Store original timestamp info for later analysis if not already present
                            if "original_timestamp" not in df.columns:
                                df["original_timestamp"] = df.iloc[:, 0].astype(str)

                            # Process timestamp columns
                            df = self._process_timestamp_columns(df)

                            return df
                        else:
                            logger.warning(f"Empty dataframe for {date.date()}")
                            return None
            except Exception as e:
                logger.error(
                    f"Error processing zip file {temp_file_path}: {str(e)}",
                    exc_info=True,
                )
                return None
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Unexpected error processing {date.date()}: {str(e)}")
            return None

    def _download_data(
        self,
        start_time: datetime,
        end_time: datetime,
        columns: Optional[Sequence[str]] = None,
    ) -> TimestampedDataFrame:
        """Download data for a specific time range.

        This method handles the core logic for retrieving data from Binance Vision API:
        1. It downloads individual daily files in parallel
        2. Merges them together in chronological order
        3. Handles day boundary transitions carefully to ensure data continuity
        4. Uses REST API to fill specific gaps at day boundaries when detected

        The day boundary handling is critical because:
        - For most intervals, the CSV files have continuous data when combined
        - However, for hourly (1h) klines, the raw CSV files typically start at 01:00:00
          with the midnight (00:00:00) record missing completely
        - When day boundary gaps are detected, REST API is used to fetch just those specific missing points
        - This ensures complete data without requiring interpolation

        Args:
            start_time: Start time for data
            end_time: End time for data
            columns: Optional columns to include in the result

        Returns:
            TimestampedDataFrame with data or empty DataFrame if download failed
        """
        try:
            # Ensure start and end times are in UTC
            start_time = start_time.astimezone(timezone.utc)
            end_time = end_time.astimezone(timezone.utc)

            # Calculate date range
            start_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
            days_delta = (end_date - start_date).days + 1
            logger.debug(f"Requested date range spans {days_delta} days")

            # Log information about large requests but don't limit them
            if days_delta > 90:
                logger.info(
                    f"Processing a large date range of {days_delta} days with parallel downloads."
                )

            # Log the date range
            logger.debug(
                f"Fetching Vision data: {self.symbol} {self.interval} - {start_date.date()} to {end_date.date()}"
            )

            # Skip the time boundary alignment since it seems incompatible with string intervals
            try:
                logger.debug(
                    f"Skipping time boundary alignment for interval: {self.interval}"
                )
                # Just use the original times
                aligned_start, aligned_end = start_time, end_time
            except Exception as e:
                logger.error(f"Error with time handling: {e}")
                # Fall back to original times
                aligned_start, aligned_end = start_time, end_time

            # Prepare to download each day in parallel (handles both single and multi-day cases)
            logger.debug(f"Will download {days_delta} days of data")
            dates_to_download = []

            # Prepare date list up front
            current_date = start_date
            while current_date <= end_date:
                dates_to_download.append(current_date)
                current_date += timedelta(days=1)

            # Calculate the number of days to download in parallel
            max_workers = min(MAXIMUM_CONCURRENT_DOWNLOADS, days_delta)
            logger.debug(
                f"Using ThreadPoolExecutor with {max_workers} workers for parallel downloads"
            )

            # Initialize results container
            day_results: Dict[datetime, Optional[pd.DataFrame]] = {}
            day_dates = []

            # Download data in parallel using ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                # Submit all download tasks
                future_to_date = {
                    executor.submit(self._download_file, date): date
                    for date in dates_to_download
                }

                # Track completed downloads
                completed = 0

                # Process results as they complete
                for future in as_completed(future_to_date):
                    date = future_to_date[future]
                    completed += 1

                    try:
                        df = future.result()
                        day_results[date] = df

                        if df is not None and not df.empty:
                            # Store the date for analysis
                            try:
                                day_date = df["open_time"].iloc[0].date()
                                day_dates.append(day_date)
                            except (KeyError, IndexError, AttributeError) as e:
                                logger.warning(
                                    f"Error extracting date from dataframe: {e}"
                                )

                            # Store original timestamp info for later analysis if not already present
                            if "original_timestamp" not in df.columns:
                                df["original_timestamp"] = df["open_time"].astype(str)

                            logger.debug(
                                f"Downloaded data for {date.date()}: {len(df)} records ({completed}/{len(dates_to_download)})"
                            )
                        else:
                            # Calculate days difference for a more informative message
                            now = datetime.now(timezone.utc)
                            days_difference = (now.date() - date.date()).days

                            if days_difference <= 2:
                                logger.warning(
                                    f"No Vision API data found for {self.symbol} on {date.date()} ({completed}/{len(dates_to_download)}) - recent data will failover to REST API"
                                )
                            else:
                                logger.warning(
                                    f"No data found for {self.symbol} on {date.date()} ({completed}/{len(dates_to_download)})"
                                )
                    except Exception as e:
                        logger.error(f"Error downloading data for {date.date()}: {e}")
                        day_results[date] = None

            # Extract all valid dataframes
            dfs = [df for df in day_results.values() if df is not None and not df.empty]

            # Check if we got any data
            if not dfs:
                # Check if the date range is recent (within 2 days of now)
                now = datetime.now(timezone.utc)
                end_day_diff = (now.date() - end_date.date()).days

                if end_day_diff <= 2:
                    logger.warning(
                        f"No Vision API data found for {self.symbol} in date range {start_date.date()} to {end_date.date()} - failover to REST API will be attempted"
                    )
                else:
                    logger.warning(
                        f"No data found for {self.symbol} in date range {start_date.date()} to {end_date.date()}"
                    )
                return self._create_empty_dataframe()

            # Combine all dataframes
            logger.debug(f"Concatenating {len(dfs)} DataFrames")
            combined_df = pd.concat(dfs, ignore_index=True)

            try:
                # Create a TimeStampedDataFrame with a proper index
                combined_df.reset_index(drop=True, inplace=True)

                # Log some basic information about the raw data
                logger.debug(f"Raw combined data has {len(combined_df)} records")
                if not combined_df.empty:
                    logger.debug(
                        f"Time range: {combined_df['open_time'].min()} to {combined_df['open_time'].max()}"
                    )

                    # Count unique days
                    unique_days = combined_df["open_time"].dt.date.unique()
                    logger.debug(f"Data spans {len(unique_days)} unique days")

                    # Print first and last rows of each day to help diagnose boundary issues
                    first_times = {}
                    last_times = {}
                    for day in sorted(unique_days):
                        day_data = combined_df[combined_df["open_time"].dt.date == day]
                        if not day_data.empty:
                            first_row = day_data.iloc[0]
                            last_row = day_data.iloc[-1]
                            first_times[day] = first_row["open_time"]
                            last_times[day] = last_row["open_time"]
                            logger.debug(
                                f"Day {day}: First record at {first_row['open_time'].strftime('%H:%M:%S')}, Last record at {last_row['open_time'].strftime('%H:%M:%S')}, Total: {len(day_data)}"
                            )

                    # Special detection for hourly data patterns
                    if self.interval_obj == Interval.HOUR_1:
                        first_hours = [dt.hour for dt in first_times.values()]
                        if all(hour == 1 for hour in first_hours):
                            logger.info(
                                "Detected hourly (1h) kline pattern: All days start at 01:00:00, missing midnight records. "
                                "This is a known limitation of Binance Vision API hourly data files."
                            )

                # Get expected interval in seconds for gap detection
                expected_interval = self._get_interval_seconds(self.interval)

                # Sort by open_time to ensure chronological order
                combined_df = combined_df.sort_values("open_time")

                # Calculate time differences between consecutive rows for gap detection only
                combined_df.loc[:, "time_diff"] = (
                    combined_df["open_time"].diff().dt.total_seconds()
                )

                # Track gaps for diagnostic purposes only (no fixing/interpolation)
                missing_midnight_detected = False

                for i in range(1, len(combined_df)):
                    prev_row = combined_df.iloc[i - 1]
                    curr_row = combined_df.iloc[i]

                    if (
                        curr_row["time_diff"] is not None
                        and curr_row["time_diff"] > expected_interval * 1.5
                    ):
                        # This is a gap in the data
                        prev_time = prev_row["open_time"]
                        curr_time = curr_row["open_time"]

                        # Special handling for day boundaries
                        if prev_time.date() != curr_time.date():
                            # For day boundaries, check if there's really a gap
                            # Check specifically for a missing midnight (00:00:00) timestamp
                            midnight_time = datetime.combine(
                                curr_time.date(),
                                datetime.min.time(),
                                tzinfo=timezone.utc,
                            )

                            # Check if the midnight timestamp exists in our dataset
                            midnight_exists = any(
                                abs((t - midnight_time).total_seconds()) < 1
                                for t in combined_df["open_time"]
                            )

                            if (
                                not midnight_exists
                                and prev_time.hour == 23
                                and curr_time.hour > 0
                            ):
                                missing_midnight_detected = True

                                # Log detailed information about the gap
                                if self.interval_obj == Interval.HOUR_1:
                                    logger.debug(
                                        f"Day boundary gap at {prev_time.date()} to {curr_time.date()}: missing midnight record. "
                                        f"This is expected with hourly klines from Vision API files which typically start at 01:00:00."
                                    )
                                else:
                                    logger.debug(
                                        f"Day boundary gap detected: {prev_time} → {curr_time}, "
                                        f"({curr_row['time_diff']:.1f}s, expected {expected_interval:.1f}s)"
                                    )
                            else:
                                logger.debug(
                                    f"Day boundary transition from {prev_time} → {curr_time} "
                                    f"(midnight record {'exists' if midnight_exists else 'missing'})"
                                )
                        else:
                            # Regular (non-boundary) gap
                            logger.debug(
                                f"Gap detected: {prev_time} → {curr_time} "
                                f"({curr_row['time_diff']:.1f}s, expected {expected_interval:.1f}s)"
                            )

                # Add a special note if using hourly interval and midnight gaps were detected
                if self.interval_obj == Interval.HOUR_1 and missing_midnight_detected:
                    logger.info(
                        "Midnight (00:00:00) records are missing in the hourly (1h) data from Binance Vision API CSV files. "
                        "This is a known limitation but no interpolation is needed as the day boundary is properly handled."
                    )
                elif missing_midnight_detected:
                    logger.info(
                        "Some midnight (00:00:00) records appear to be missing at day boundaries. "
                        "This should be rare with 1-minute data but should be properly handled without interpolation."
                    )

                # Drop the time_diff column as we don't need it anymore
                if "time_diff" in combined_df.columns:
                    combined_df = combined_df.drop(columns=["time_diff"])

                # Ensure the DataFrame is sorted by time
                combined_df = combined_df.sort_values("open_time").reset_index(
                    drop=True
                )

            except Exception as e:
                logger.warning(f"Error during data analysis: {e}")

            # Filter by time range
            filtered_df = filter_dataframe_by_time(
                combined_df, aligned_start, aligned_end, "open_time"
            )

            # Report data coverage
            if not filtered_df.empty:
                actual_start = filtered_df["open_time"].iloc[0]
                actual_end = filtered_df["open_time"].iloc[-1]
                record_count = len(filtered_df)

                # Calculate expected count based on interval
                interval_seconds = self._get_interval_seconds(self.interval)
                total_seconds = (actual_end - actual_start).total_seconds()
                expected_count = int(total_seconds / interval_seconds) + 1

                # Calculate coverage percentage
                if expected_count > 0:
                    coverage_percent = (record_count / expected_count) * 100
                    logger.debug(
                        f"Data coverage: {record_count} records / {expected_count} expected ({coverage_percent:.1f}%)"
                    )

                logger.debug(f"Final time range: {actual_start} to {actual_end}")

                # Analyze day boundaries in the filtered data
                boundary_gaps = []
                unique_days = filtered_df["open_time"].dt.date.unique()
                for i in range(len(unique_days) - 1):
                    curr_day = unique_days[i]
                    next_day = unique_days[i + 1]

                    # Get last record of current day
                    curr_day_data = filtered_df[
                        filtered_df["open_time"].dt.date == curr_day
                    ]
                    next_day_data = filtered_df[
                        filtered_df["open_time"].dt.date == next_day
                    ]

                    if not curr_day_data.empty and not next_day_data.empty:
                        last_of_day = curr_day_data.iloc[-1]["open_time"]
                        first_of_next = next_day_data.iloc[0]["open_time"]
                        time_diff = (first_of_next - last_of_day).total_seconds()

                        # Check for midnight record at next day boundary
                        midnight_time = datetime.combine(
                            next_day, datetime.min.time(), tzinfo=timezone.utc
                        )

                        # Check if midnight record exists
                        midnight_exists = any(
                            abs((t - midnight_time).total_seconds()) < 1
                            for t in filtered_df["open_time"]
                        )

                        # Only report as a gap if the midnight record is missing and time difference is large
                        if time_diff > interval_seconds * 1.5 and not midnight_exists:
                            logger.debug(
                                f"Potential gap at day boundary: {curr_day} to {next_day}, "
                                f"Last record at {last_of_day.strftime('%H:%M:%S')}, "
                                f"First record at {first_of_next.strftime('%H:%M:%S')}, "
                                f"Difference: {time_diff}s (expected {interval_seconds}s)"
                            )
                            boundary_gaps.append(
                                {
                                    "start_time": last_of_day,
                                    "end_time": first_of_next,
                                    "missing_time": midnight_time,
                                    "expected_interval": interval_seconds,
                                }
                            )
                        else:
                            logger.debug(
                                f"Day boundary transition from {curr_day} to {next_day} "
                                f"(midnight record {'exists' if midnight_exists else 'missing'})"
                            )

                # Fill gaps at day boundaries if any were detected
                if boundary_gaps:
                    filled_df = self._fill_boundary_gaps_with_rest(
                        filtered_df, boundary_gaps
                    )
                    if filled_df is not None:
                        filtered_df = filled_df
                        logger.info(
                            f"Filled {len(boundary_gaps)} day boundary gaps with REST API data"
                        )
                    else:
                        logger.warning(
                            "Failed to fill day boundary gaps with REST API data"
                        )
            else:
                logger.warning(
                    f"No data found for {self.symbol} in filtered range {aligned_start} to {aligned_end}"
                )

            logger.debug(
                f"Downloaded {len(filtered_df)} records for {self.symbol} from {aligned_start} to {aligned_end}"
            )

            # Standardize column names
            filtered_df = standardize_column_names(filtered_df)

            # Select specific columns if requested
            if columns is not None:
                all_cols = set(filtered_df.columns)
                missing_cols = set(columns) - all_cols
                if missing_cols:
                    logger.warning(
                        f"Requested columns not found: {missing_cols}. Available: {all_cols}"
                    )
                filtered_df = filtered_df[[col for col in columns if col in all_cols]]

            return filtered_df

        except Exception as e:
            logger.error(f"Error downloading data: {e}")
            return self._create_empty_dataframe()

    def _fill_boundary_gaps_with_rest(
        self, df: pd.DataFrame, boundary_gaps: List[Dict[str, Any]]
    ) -> Optional[pd.DataFrame]:
        """Fill day boundary gaps using REST API data.

        This method fetches just the specific missing records at day boundaries using
        the REST API, then merges them with the original data from Vision API.

        Args:
            df: DataFrame with Vision API data that has gaps
            boundary_gaps: List of gap information dictionaries

        Returns:
            DataFrame with gaps filled, or None if filling failed
        """
        try:
            from core.sync.rest_data_client import RestDataClient
            from utils.market_constraints import Interval

            # Create a REST client for fetching the missing data
            rest_client = RestDataClient(
                market_type=self.market_type,
                symbol=self.symbol,
                interval=self.interval_obj,
            )

            # Create a list to hold the gap data we'll fetch
            gap_dfs = []

            # Include the original data
            if not df.empty:
                gap_dfs.append(df)

            # For each gap, fetch the specific missing data
            for gap in boundary_gaps:
                # Buffer the request times slightly to ensure we get the missing point
                buffer_seconds = gap["expected_interval"] * 0.5

                # Calculate precise start and end times for the REST request
                # Fetch a bit before and after the actual gap to ensure we get the needed data
                gap_start = gap["start_time"] - timedelta(seconds=buffer_seconds)
                gap_end = gap["end_time"] + timedelta(seconds=buffer_seconds)

                logger.debug(
                    f"Fetching gap data from REST API: {gap_start} to {gap_end} "
                    f"(to fill missing {gap['missing_time']})"
                )

                # Fetch the gap data using REST API
                gap_data = rest_client.fetch(
                    symbol=self.symbol,
                    interval=self.interval_obj,
                    start_time=gap_start,
                    end_time=gap_end,
                )

                if not gap_data.empty:
                    # Check if we got the missing midnight record
                    midnight_time = gap["missing_time"]
                    midnight_records = gap_data[
                        (gap_data["open_time"] - midnight_time).abs()
                        < timedelta(seconds=1)
                    ]

                    if not midnight_records.empty:
                        logger.debug(
                            f"Successfully fetched missing midnight record for {midnight_time.date()}"
                        )
                        gap_dfs.append(gap_data)
                    else:
                        logger.warning(
                            f"REST API did not return the expected midnight record for {midnight_time.date()}"
                        )

            # If we have gap data, merge it with the original data
            if len(gap_dfs) > 1:  # More than just the original df
                # Concatenate all data
                merged_df = pd.concat(gap_dfs, ignore_index=True)

                # Remove duplicates and sort
                merged_df = merged_df.drop_duplicates(subset=["open_time"])
                merged_df = merged_df.sort_values("open_time").reset_index(drop=True)

                return merged_df

            # If we didn't add any gap data, return the original
            return df

        except Exception as e:
            logger.error(f"Error filling boundary gaps with REST API: {e}")
            import traceback

            logger.error(f"Traceback: {traceback.format_exc()}")
            return None

    def fetch(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> TimestampedDataFrame:
        """Fetch data for a specific time range.

        Args:
            start_time: Start time for data
            end_time: End time for data

        Returns:
            TimestampedDataFrame with data
        """
        try:
            # Enforce consistent timezone for time boundaries
            start_time = start_time.astimezone(timezone.utc)
            end_time = end_time.astimezone(timezone.utc)

            # Calculate date range
            delta_days = (end_time - start_time).days + 1
            logger.debug(
                f"Requested date range spans {delta_days} days from {start_time} to {end_time}"
            )

            # Log if it's a large request
            if delta_days > 90:
                logger.info(
                    f"Processing a large date range of {delta_days} days with parallel downloads."
                )

            # Download data
            try:
                logger.debug(f"Calling _download_data from {start_time} to {end_time}")
                return self._download_data(start_time, end_time)
            except Exception as e:
                logger.error(f"Error in _download_data: {e}")
                import traceback

                logger.error(f"Traceback: {traceback.format_exc()}")
                raise
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return self._create_empty_dataframe()

    @staticmethod
    def fetch_multiple(
        symbols: List[str],
        start_time: datetime,
        end_time: datetime,
        interval: str = "1m",
        market_type: Union[str, MarketType] = MarketType.SPOT,
        max_workers: Optional[int] = None,
    ) -> Dict[str, TimestampedDataFrame]:
        """Fetch data for multiple symbols in parallel.

        Args:
            symbols: List of trading symbols to fetch data for
            start_time: Start time for data
            end_time: End time for data
            interval: Kline interval e.g. '1s', '1m'
            market_type: Market type (SPOT, FUTURES_USDT, FUTURES_COIN) or string
            max_workers: Maximum number of parallel workers (defaults to min(MAXIMUM_CONCURRENT_DOWNLOADS, len(symbols)))

        Returns:
            Dictionary mapping symbols to their respective DataFrames
        """
        if not symbols:
            logger.warning("No symbols provided to fetch_multiple")
            return {}

        # Calculate effective number of workers
        if max_workers is None:
            max_workers = min(MAXIMUM_CONCURRENT_DOWNLOADS, len(symbols))
        else:
            max_workers = min(max_workers, MAXIMUM_CONCURRENT_DOWNLOADS, len(symbols))

        # Calculate date range for logging
        delta_days = (end_time - start_time).days + 1

        # Log large requests but don't limit them
        if delta_days > 90:
            logger.info(
                f"Processing a large date range of {delta_days} days for {len(symbols)} symbols. This is supported with parallel downloads."
            )

        logger.info(
            f"Fetching data for {len(symbols)} symbols using {max_workers} parallel workers"
        )

        results: Dict[str, TimestampedDataFrame] = {}

        # Define worker function to download data for a single symbol
        def download_worker(symbol: str) -> Tuple[str, TimestampedDataFrame]:
            try:
                with VisionDataClient(
                    symbol=symbol, interval=interval, market_type=market_type
                ) as client:
                    df = client.fetch(start_time, end_time)
                return symbol, df
            except Exception as e:
                logger.error(f"Error fetching data for {symbol}: {e}")
                # Return empty dataframe on error
                return symbol, VisionDataClient._create_empty_dataframe()

        # Use ThreadPoolExecutor to parallelize downloads across symbols
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {
                executor.submit(download_worker, symbol): symbol for symbol in symbols
            }

            # Process results as they complete
            for i, future in enumerate(as_completed(future_to_symbol)):
                symbol = future_to_symbol[future]
                try:
                    symbol_result, df = future.result()
                    results[symbol_result] = df
                    logger.info(
                        f"Completed download for {symbol} ({i+1}/{len(symbols)}): {len(df)} records"
                    )
                except Exception as e:
                    logger.error(f"Error processing result for {symbol}: {e}")
                    # Create empty dataframe for failed symbols
                    results[symbol] = VisionDataClient._create_empty_dataframe()

        return results
