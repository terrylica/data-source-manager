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
from typing import Optional, Sequence, TypeVar, Generic, Union
import os
import tempfile
import zipfile
import httpx

import pandas as pd

from utils.logger_setup import logger
from utils.market_constraints import Interval, MarketType
from utils.time_utils import (
    align_time_boundaries,
    filter_dataframe_by_time,
    get_interval_seconds,
)
from utils.config import (
    create_empty_dataframe,
    standardize_column_names,
)
from core.sync.vision_constraints import (
    TimestampedDataFrame,
    FileType,
    get_vision_url,
    detect_timestamp_unit,
    MICROSECOND_DIGITS,
    MILLISECOND_DIGITS,
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

    def _create_empty_dataframe(self) -> TimestampedDataFrame:
        """Create an empty dataframe with the correct structure.

        Returns:
            Empty TimestampedDataFrame with the correct columns
        """
        # Define standard OHLCV columns directly
        columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base_asset_volume",
            "taker_buy_quote_asset_volume",
        ]

        df = pd.DataFrame(columns=columns)
        df["open_time_us"] = pd.Series(dtype="int64")
        df["close_time_us"] = pd.Series(dtype="int64")

        # Set index to open_time_us and convert to TimestampedDataFrame
        df = df.set_index("open_time_us")

        return TimestampedDataFrame(df)

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
                            # Check timestamp format - determine if microseconds or milliseconds
                            if len(df) > 0:
                                first_ts = df.iloc[
                                    0, 0
                                ]  # First timestamp in first column

                                try:
                                    # Detect timestamp unit using the standardized function
                                    timestamp_unit = detect_timestamp_unit(first_ts)

                                    if timestamp_unit == "us":
                                        logger.debug(
                                            f"Using microsecond timestamp unit for {self.symbol}"
                                        )
                                        # Convert microseconds to milliseconds for compatibility
                                        df["open_time_ms"] = df.iloc[:, 0] // 1000
                                        df["close_time_ms"] = df.iloc[:, 6] // 1000
                                    else:
                                        logger.debug(
                                            f"Using millisecond timestamp unit for {self.symbol}"
                                        )
                                        df["open_time_ms"] = df.iloc[:, 0]
                                        df["close_time_ms"] = df.iloc[:, 6]

                                    # Log the first and last timestamps for debugging
                                    logger.debug(
                                        f"First timestamp: {first_ts} ({timestamp_unit})"
                                    )
                                    if len(df) > 1:
                                        last_ts = df.iloc[-1, 0]
                                        logger.debug(
                                            f"Last timestamp: {last_ts} ({timestamp_unit})"
                                        )
                                except ValueError as e:
                                    logger.warning(
                                        f"Error detecting timestamp unit: {e}"
                                    )
                                    # Default to milliseconds for compatibility
                                    logger.debug(
                                        f"Defaulting to millisecond timestamp unit for {self.symbol}"
                                    )
                                    df["open_time_ms"] = df.iloc[:, 0]
                                    df["close_time_ms"] = df.iloc[:, 6]

                            # Standardize column names
                            column_names = [
                                "open_time_us",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "close_time_us",
                                "quote_asset_volume",
                                "number_of_trades",
                                "taker_buy_base_asset_volume",
                                "taker_buy_quote_asset_volume",
                                "ignore",
                            ]

                            # Rename columns if the count matches
                            if len(df.columns) == len(column_names):
                                df.columns = column_names

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

            # Check if date range is reasonable
            if days_delta > 180:
                logger.warning(
                    f"Requested date range is very large: {days_delta} days. Consider breaking this into smaller requests."
                )
                max_days = 90
                # Adjust to 90 days max for safety
                if days_delta > max_days:
                    logger.warning(
                        f"Limiting to {max_days} days for performance and safety"
                    )
                    end_date = start_date + timedelta(days=max_days - 1)
                    days_delta = max_days

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

            # If start and end are on the same day, just download once
            if start_date == end_date:
                logger.debug(f"Will download 1 days of data")
                df = self._download_file(start_date)
                if df is None or df.empty:
                    logger.warning(
                        f"No data found for {self.symbol} on {start_date.date()}"
                    )
                    return self._create_empty_dataframe()

                # Convert timestamps to datetime
                if "open_time_ms" in df.columns:
                    # Use the millisecond timestamps we created during download
                    df.loc[:, "open_time"] = pd.to_datetime(
                        df["open_time_ms"], unit="ms", utc=True
                    )
                    df.loc[:, "close_time"] = pd.to_datetime(
                        df["close_time_ms"], unit="ms", utc=True
                    )
                else:
                    # Fallback to using the original columns directly
                    df.loc[:, "open_time"] = pd.to_datetime(
                        df["open_time_us"], unit="us", utc=True
                    )
                    df.loc[:, "close_time"] = pd.to_datetime(
                        df["close_time_us"], unit="us", utc=True
                    )

                # Filter for time range
                df = filter_dataframe_by_time(
                    df, aligned_start, aligned_end, "open_time"
                )
                logger.debug(
                    f"Downloaded {len(df)} records for {self.symbol} from {aligned_start} to {aligned_end}"
                )

                # Standardize column names
                df = standardize_column_names(df)

                # Select specific columns if requested
                if columns is not None:
                    all_cols = set(df.columns)
                    missing_cols = set(columns) - all_cols
                    if missing_cols:
                        logger.warning(
                            f"Requested columns not found: {missing_cols}. Available: {all_cols}"
                        )
                    df = df[[col for col in columns if col in all_cols]]

                return df

            # For multiple days, download each day and concatenate
            logger.debug(f"Will download {days_delta} days of data")
            dfs = []
            day_dates = []

            # Setup iteration
            current_date = start_date
            dates_to_download = []

            # Prepare date list up front for clearer logging
            while current_date <= end_date:
                dates_to_download.append(current_date)
                current_date += timedelta(days=1)

            logger.debug(
                f"Downloading {len(dates_to_download)} days for {self.symbol} {self.interval}"
            )
            logger.debug(
                f"Date range: {dates_to_download[0].date()} to {dates_to_download[-1].date()}"
            )

            # Iterate through each date
            for i, current_date in enumerate(dates_to_download):
                df = self._download_file(current_date)
                if df is None or df.empty:
                    logger.warning(
                        f"No data found for {self.symbol} on {current_date.date()} ({i+1}/{len(dates_to_download)})"
                    )
                    continue

                # Convert timestamps to datetime
                if "open_time_ms" in df.columns:
                    # Use the millisecond timestamps we created during download
                    df.loc[:, "open_time"] = pd.to_datetime(
                        df["open_time_ms"], unit="ms", utc=True
                    )
                    df.loc[:, "close_time"] = pd.to_datetime(
                        df["close_time_ms"], unit="ms", utc=True
                    )
                else:
                    # Fallback to using the original columns directly
                    df.loc[:, "open_time"] = pd.to_datetime(
                        df["open_time_us"], unit="us", utc=True
                    )
                    df.loc[:, "close_time"] = pd.to_datetime(
                        df["close_time_us"], unit="us", utc=True
                    )

                dfs.append(df)

                if not df.empty:
                    # Store the date for analysis
                    day_date = df["open_time"].iloc[0].date()
                    day_dates.append(day_date)

                    logger.debug(
                        f"Downloaded data for {current_date.date()}: {len(df)} records ({i+1}/{len(dates_to_download)})"
                    )

                    # Store original timestamp info for later analysis if not already present
                    if "original_timestamp" not in df.columns:
                        df["original_timestamp"] = df["open_time_us"].astype(str)

                if i > 0 and day_dates[i] != day_dates[i - 1] + timedelta(days=1):
                    if i < len(day_dates):
                        logger.debug(
                            f"Date discontinuity: {day_dates[i-1]} -> {day_dates[i]}"
                        )

            if not dfs:
                logger.warning(
                    f"No data found for {self.symbol} in date range {start_date.date()} to {end_date.date()}"
                )
                return self._create_empty_dataframe()

            # Combine all dataframes
            logger.debug(f"Concatenating {len(dfs)} DataFrames")
            combined_df = pd.concat(dfs, ignore_index=True)

            try:
                # First, sort by open_time to ensure chronological order
                combined_df = combined_df.sort_values("open_time")

                # Calculate time differences between consecutive rows
                combined_df.loc[:, "time_diff"] = (
                    combined_df["open_time"].diff().dt.total_seconds()
                )

                # Get expected interval in seconds
                expected_interval = get_interval_seconds(self.interval)

                # Look for gaps significantly larger than expected interval at day boundaries
                # Focus on midnight transitions (23:00-01:00)
                combined_df.loc[:, "hour"] = combined_df["open_time"].dt.hour
                combined_df.loc[:, "minute"] = combined_df["open_time"].dt.minute
                combined_df.loc[:, "day"] = combined_df["open_time"].dt.day
                combined_df.loc[:, "month"] = combined_df["open_time"].dt.month
                combined_df.loc[:, "year"] = combined_df["open_time"].dt.year

                # List to store any midnight records that actually need to be added
                midnight_records = []

                # Detect and repair day boundary gaps
                for i in range(1, len(combined_df)):
                    prev_row = combined_df.iloc[i - 1]
                    curr_row = combined_df.iloc[i]

                    # Only check time differences significantly larger than expected
                    if (
                        curr_row["time_diff"] is not None
                        and curr_row["time_diff"] > expected_interval * 1.5
                    ):
                        # Focus on transitions between 23:xx and 00:xx/01:xx (day boundaries)
                        if prev_row["hour"] == 23 and curr_row["hour"] in [0, 1]:
                            # Calculate the expected midnight timestamp
                            prev_date = prev_row["open_time"].date()
                            curr_date = curr_row["open_time"].date()

                            # Only proceed if dates are consecutive
                            if curr_date == prev_date + timedelta(days=1):
                                # Calculate expected midnight datetime
                                midnight = datetime.combine(
                                    curr_date, datetime.min.time(), tzinfo=timezone.utc
                                )

                                # Determine if we actually have a missing midnight record
                                # Sometimes we already have records very close to midnight
                                nearest_midnight = combined_df[
                                    (
                                        combined_df["hour"] == 0
                                        and combined_df["minute"] < 1
                                    )
                                    | (
                                        combined_df["hour"] == 23
                                        and combined_df["minute"] > 58
                                    )
                                ]
                                nearest_midnight = nearest_midnight[
                                    combined_df["day"] == curr_date.day
                                    or combined_df["day"] == prev_date.day
                                ]

                                if not nearest_midnight.empty:
                                    # We have a record very close to midnight already, no need for interpolation
                                    logger.debug(
                                        f"Day boundary at index {i} has midnight record: "
                                        f"{prev_row['open_time']} → {midnight} → {curr_row['open_time']}"
                                    )
                                    continue

                                # Calculate gap size at day boundary in seconds
                                gap_in_seconds = curr_row["time_diff"]

                                # If the gap is very close to the expected interval, it's not really a gap
                                # For example, the expected gap between 23:59:59 and 00:00:00 is just 1 second
                                if abs(gap_in_seconds - expected_interval) < 2:
                                    logger.debug(
                                        f"Day boundary transition without gap at index {i}: "
                                        f"{prev_row['open_time']} → {curr_row['open_time']} "
                                        f"({curr_row['time_diff']:.1f}s)"
                                    )
                                    continue

                                # Log true gaps for debugging
                                logger.warning(
                                    f"True day boundary gap detected at index {i}: "
                                    f"{prev_row['open_time']} → {curr_row['open_time']} "
                                    f"({curr_row['time_diff']:.1f}s, expected {expected_interval:.1f}s)"
                                )

                                # Now we need to create a midnight record through interpolation
                                interpolated_row = prev_row.copy()
                                interpolated_row["open_time"] = midnight

                                # Calculate interpolation weight (what % of the way from prev to curr time)
                                time_diff_seconds = (
                                    curr_row["open_time"] - prev_row["open_time"]
                                ).total_seconds()
                                prev_to_midnight_seconds = (
                                    midnight - prev_row["open_time"]
                                ).total_seconds()
                                weight = prev_to_midnight_seconds / time_diff_seconds

                                # Linear interpolation for numeric columns
                                for col in ["open", "high", "low", "close", "volume"]:
                                    if col in prev_row and col in curr_row:
                                        try:
                                            interpolated_row[col] = prev_row[
                                                col
                                            ] + weight * (curr_row[col] - prev_row[col])
                                        except Exception as e:
                                            logger.warning(
                                                f"Error interpolating column {col}: {e}"
                                            )

                                # Add boundary flag for reference
                                interpolated_row["boundary_record"] = (
                                    "interpolated_midnight"
                                )
                                midnight_records.append(interpolated_row)
                            else:
                                logger.debug(
                                    f"Day boundary transition without gap at index {i}: "
                                    f"{prev_row['open_time']} → {curr_row['open_time']} "
                                    f"({curr_row['time_diff']:.1f}s)"
                                )

                # Add any interpolated midnight records
                if midnight_records:
                    logger.debug(
                        f"Adding {len(midnight_records)} interpolated midnight records"
                    )
                    combined_df = pd.concat(
                        [combined_df, pd.DataFrame(midnight_records)], ignore_index=True
                    )

                    # Sort and reset index
                    combined_df = combined_df.sort_values("open_time").reset_index(
                        drop=True
                    )

            except Exception as e:
                logger.warning(f"Error during day boundary analysis: {e}")

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
                interval_seconds = get_interval_seconds(self.interval)
                expected_count = (
                    int((actual_end - actual_start).total_seconds() / interval_seconds)
                    + 1
                )
                coverage_percent = (record_count / expected_count) * 100
                logger.debug(
                    f"Data coverage: {record_count} records / {expected_count} expected ({coverage_percent:.1f}%)"
                )
                logger.debug(f"Time range: {actual_start} to {actual_end}")
            else:
                logger.warning(
                    f"No data found for {self.symbol} in filtered range {aligned_start} to {aligned_end}"
                )

            # Ensure the DataFrame is sorted by time
            filtered_df = filtered_df.sort_values("open_time").reset_index(drop=True)

            logger.debug(
                f"Downloaded {len(filtered_df)} records for {self.symbol} from {aligned_start} to {aligned_end}"
            )

            # Drop temporary columns used for analysis
            cols_to_drop = [
                "time_diff",
                "hour",
                "minute",
                "day",
                "month",
                "year",
                "boundary_record",
                "original_timestamp",
            ]
            for col in cols_to_drop:
                if col in filtered_df.columns:
                    filtered_df = filtered_df.drop(columns=[col])

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

    def fetch(
        self, start_time: datetime, end_time: datetime, max_days: int = 90
    ) -> TimestampedDataFrame:
        """Fetch data for a specific time range.

        Args:
            start_time: Start time for data
            end_time: End time for data
            max_days: Maximum number of days to fetch at once

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

            # Check if date range is reasonable
            if delta_days > max_days:
                logger.warning(
                    f"Requested date range of {delta_days} days exceeds limit of {max_days} days"
                )
                logger.warning(f"Limiting to {max_days} days from {start_time}")
                end_time = start_time + timedelta(days=max_days)
                delta_days = max_days

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

    def close(self) -> None:
        """Close the client and release resources."""
        if hasattr(self, "_client") and self._client:
            try:
                self._client.close()
            except Exception as e:
                logger.warning(f"Error closing httpx client: {e}")
