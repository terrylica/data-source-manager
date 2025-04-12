#!/usr/bin/env python
"""Simple benchmark script to verify Vision API performance improvements.

This script measures the download performance of the VisionDataClient
with the optimized settings and compares it with baseline metrics.
"""

import time
import concurrent.futures
import argparse
import threading
import os
import tempfile
import zipfile
import json
import subprocess
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from enum import Enum, auto

import httpx
import pandas as pd
import aioboto3
import nest_asyncio
from aiobotocore.config import AioConfig
import botocore
import boto3  # Add official boto3

from core.sync.vision_data_client import VisionDataClient
from core.sync.vision_constraints import (
    detect_timestamp_unit,
    MICROSECOND_DIGITS,
    MILLISECOND_DIGITS,
    FileType,
)
from utils.time_utils import enforce_utc_timezone
from utils.logger_setup import logger
from rich import print


class DownloadMethod(Enum):
    """Method used to download data."""

    VISION_CLIENT = auto()
    HTTPX_CHROME = auto()
    HTTPX_FIREFOX = auto()
    HTTPX_SAFARI = auto()
    AWS_CLI = auto()
    AIOBOTO3 = auto()  # New method for aioboto3
    BOTO3 = auto()  # New method for official boto3


# User agent strings for different browsers
USER_AGENTS = {
    DownloadMethod.HTTPX_CHROME: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    DownloadMethod.HTTPX_FIREFOX: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/117.0",
    DownloadMethod.HTTPX_SAFARI: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15",
}


def get_vision_url(symbol, interval, date, market_type="spot"):
    """Generate URL for Binance Vision data."""
    # Convert date to string
    date_str = date.strftime("%Y-%m-%d")

    # Determine URL components based on interval
    if interval == "1s":
        file_prefix = f"{symbol.upper()}-1s"
    else:
        file_prefix = f"{symbol.upper()}-{interval}"

    # Construct the URL - exactly match the VisionDataClient URL pattern
    url = f"https://data.binance.vision/data/{market_type}/daily/klines/{symbol.upper()}/{interval}/{file_prefix}-{date_str}.zip"

    return url


def download_with_httpx(symbol, interval, start_time, end_time, user_agent):
    """Download data using httpx with specified user agent.

    Args:
        symbol: Trading symbol
        interval: Time interval
        start_time: Start time for data
        end_time: End time for data
        user_agent: User agent string to use

    Returns:
        Pandas DataFrame with data or None if download failed
    """
    # Use current dates
    current_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)

    logger.info(f"Date range for httpx: {current_date.date()} to {end_date.date()}")
    logger.info(
        f"Start time: {start_time.isoformat()}, End time: {end_time.isoformat()}"
    )

    all_data = []

    with httpx.Client(timeout=30.0, headers={"User-Agent": user_agent}) as client:
        while current_date <= end_date:
            url = get_vision_url(symbol, interval, current_date)

            try:
                # Download the zip file
                logger.info(f"Downloading {url}")
                response = client.get(url)
                if response.status_code != 200:
                    logger.error(
                        f"Failed to download {url}: HTTP {response.status_code}"
                    )
                    current_date += timedelta(days=1)
                    continue

                logger.info(
                    f"Successfully downloaded {url} - size: {len(response.content)} bytes"
                )

                # Process the zip file
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".zip"
                ) as temp_file:
                    temp_file.write(response.content)
                    temp_file_path = temp_file.name

                try:
                    # Extract and read the CSV
                    logger.info(f"Processing zip file: {temp_file_path}")
                    with zipfile.ZipFile(temp_file_path, "r") as zip_ref:
                        file_list = zip_ref.namelist()
                        logger.info(f"Files in zip: {file_list}")

                        if not file_list:
                            logger.error("Zip file is empty")
                            current_date += timedelta(days=1)
                            continue

                        csv_file = file_list[0]

                        # Extract to a temporary directory
                        with tempfile.TemporaryDirectory() as temp_dir:
                            logger.info(f"Extracting {csv_file} to {temp_dir}")
                            zip_ref.extract(csv_file, temp_dir)
                            csv_path = os.path.join(temp_dir, csv_file)

                            # Read the CSV file
                            logger.info(f"Reading CSV file: {csv_path}")
                            df = pd.read_csv(csv_path)
                            logger.info(f"Read {len(df)} rows from CSV")

                            # Create column names for the dataframe
                            column_names = [
                                "open_time_us",  # Microsecond timestamp
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

                            # Rename columns
                            if len(df.columns) == len(column_names):
                                df.columns = column_names

                            # Convert microseconds to milliseconds for comparison
                            if len(df) > 0:
                                first_ts = df.iloc[
                                    0, 0
                                ]  # First timestamp in first column
                                last_ts = df.iloc[
                                    -1, 0
                                ]  # Last timestamp in first column
                                logger.info(f"First timestamp in file: {first_ts}")
                                logger.info(f"Last timestamp in file: {last_ts}")

                                # Use the standardized timestamp detection function
                                try:
                                    timestamp_unit = detect_timestamp_unit(first_ts)
                                    logger.info(
                                        f"Detected timestamp unit: {timestamp_unit}"
                                    )

                                    if timestamp_unit == "us":
                                        logger.info(
                                            "Timestamps are in microseconds, converting to milliseconds"
                                        )
                                        df["open_time_ms"] = df["open_time_us"] // 1000
                                    else:
                                        logger.info("Timestamps are in milliseconds")
                                        df["open_time_ms"] = df["open_time_us"]
                                except ValueError as e:
                                    logger.warning(
                                        f"Error detecting timestamp unit: {e}"
                                    )
                                    # Default to microseconds if detection fails (safer approach)
                                    logger.info(
                                        "Defaulting to microseconds, converting to milliseconds"
                                    )
                                    df["open_time_ms"] = df["open_time_us"] // 1000

                                # Convert to datetime for display of the first/last timestamps
                                try:
                                    first_ms = df["open_time_ms"].iloc[0]
                                    last_ms = df["open_time_ms"].iloc[-1]
                                    first_dt = datetime.fromtimestamp(
                                        first_ms / 1000, tz=timezone.utc
                                    )
                                    last_dt = datetime.fromtimestamp(
                                        last_ms / 1000, tz=timezone.utc
                                    )
                                    logger.info(
                                        f"First datetime: {first_dt.isoformat()}"
                                    )
                                    logger.info(f"Last datetime: {last_dt.isoformat()}")
                                except Exception as e:
                                    logger.error(
                                        f"Error converting timestamps to datetime: {e}"
                                    )

                                # Calculate filter boundaries in milliseconds
                                start_ms = int(start_time.timestamp() * 1000)
                                end_ms = int(end_time.timestamp() * 1000)
                                logger.info(
                                    f"Filtering for timestamps between {start_ms} ms and {end_ms} ms"
                                )

                                # Filter rows by timestamp in milliseconds
                                filtered_df = df[
                                    (df["open_time_ms"] >= start_ms)
                                    & (df["open_time_ms"] <= end_ms)
                                ].copy()  # Create an explicit copy
                                logger.info(
                                    f"Filtered to {len(filtered_df)} rows in requested time range"
                                )

                                # Now convert timestamps to datetime objects
                                if len(filtered_df) > 0:
                                    logger.info(
                                        "Creating datetime objects for the filtered rows"
                                    )
                                    filtered_df.loc[:, "open_time"] = pd.to_datetime(
                                        filtered_df["open_time_ms"], unit="ms"
                                    )

                                    # Append to result
                                    all_data.append(filtered_df)
                                else:
                                    logger.warning("No rows left after filtering")
                except Exception as e:
                    logger.error(
                        f"Error processing zip file {temp_file_path}: {str(e)}",
                        exc_info=True,
                    )
                finally:
                    # Clean up temp file
                    if os.path.exists(temp_file_path):
                        logger.info(f"Removing temp file: {temp_file_path}")
                        os.unlink(temp_file_path)

            except Exception as e:
                logger.error(f"Error processing {url}: {str(e)}", exc_info=True)

            # Move to next day
            current_date += timedelta(days=1)

    # Combine all data
    if all_data:
        logger.info(f"Combining {len(all_data)} DataFrames")
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"Final result has {len(result)} rows")
        return result
    else:
        logger.warning("No data collected, returning empty DataFrame")
        return pd.DataFrame()


def download_with_aws_cli(symbol, interval, start_time, end_time):
    """Download data using AWS CLI (S3 URI).

    Args:
        symbol: Trading symbol
        interval: Time interval
        start_time: Start time for data
        end_time: End time for data

    Returns:
        Pandas DataFrame with data or None if download failed
    """
    # Use current dates
    current_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)

    logger.info(f"Date range for AWS S3: {current_date.date()} to {end_date.date()}")
    logger.info(
        f"Start time: {start_time.isoformat()}, End time: {end_time.isoformat()}"
    )

    all_data = []
    temp_dir = tempfile.mkdtemp()

    try:
        while current_date <= end_date:
            # Format date for URL
            date_str = current_date.strftime("%Y-%m-%d")

            # Determine file prefix
            if interval == "1s":
                file_prefix = f"{symbol.upper()}-1s"
            else:
                file_prefix = f"{symbol.upper()}-{interval}"

            # S3 URI pattern - match the same pattern as get_vision_url
            s3_uri = f"s3://public-binance-data/data/spot/daily/klines/{symbol.upper()}/{interval}/{file_prefix}-{date_str}.zip"

            # Local file path
            local_path = Path(temp_dir) / f"{file_prefix}-{date_str}.zip"

            try:
                # Download using aws cli
                logger.info(f"Downloading from S3: {s3_uri}")
                cmd = ["aws", "s3", "cp", s3_uri, str(local_path), "--no-sign-request"]
                process = subprocess.run(cmd, capture_output=True, text=True)

                if process.returncode != 0:
                    logger.error(f"Failed to download from S3: {process.stderr}")
                    current_date += timedelta(days=1)
                    continue

                if not local_path.exists():
                    logger.error(f"File {local_path} not found after download")
                    current_date += timedelta(days=1)
                    continue

                logger.info(f"Successfully downloaded to {local_path}")

                # Process the zip file
                with zipfile.ZipFile(local_path, "r") as zip_ref:
                    file_list = zip_ref.namelist()
                    logger.info(f"Files in zip: {file_list}")

                    if not file_list:
                        logger.error("Zip file is empty")
                        current_date += timedelta(days=1)
                        continue

                    csv_file = file_list[0]
                    csv_path = Path(temp_dir) / csv_file
                    zip_ref.extract(csv_file, temp_dir)

                    # Read the CSV file
                    logger.info(f"Reading CSV file: {csv_path}")
                    df = pd.read_csv(csv_path)
                    logger.info(f"Read {len(df)} rows from CSV")

                    # Create column names for the dataframe
                    column_names = [
                        "open_time_us",  # Microsecond timestamp
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

                    # Rename columns
                    if len(df.columns) == len(column_names):
                        df.columns = column_names

                    # Convert microseconds to milliseconds for comparison
                    if len(df) > 0:
                        first_ts = df.iloc[0, 0]  # First timestamp in first column
                        last_ts = df.iloc[-1, 0]  # Last timestamp in first column
                        logger.info(f"First timestamp in file: {first_ts}")
                        logger.info(f"Last timestamp in file: {last_ts}")

                        # Use the standardized timestamp detection function
                        try:
                            timestamp_unit = detect_timestamp_unit(first_ts)
                            logger.info(f"Detected timestamp unit: {timestamp_unit}")

                            if timestamp_unit == "us":
                                logger.info(
                                    "Timestamps are in microseconds, converting to milliseconds"
                                )
                                df["open_time_ms"] = df["open_time_us"] // 1000
                            else:
                                logger.info("Timestamps are in milliseconds")
                                df["open_time_ms"] = df["open_time_us"]
                        except ValueError as e:
                            logger.warning(f"Error detecting timestamp unit: {e}")
                            # Default to microseconds if detection fails (safer approach)
                            logger.info(
                                "Defaulting to microseconds, converting to milliseconds"
                            )
                            df["open_time_ms"] = df["open_time_us"] // 1000

                        # Convert to datetime for display of the first/last timestamps
                        try:
                            first_ms = df["open_time_ms"].iloc[0]
                            last_ms = df["open_time_ms"].iloc[-1]
                            first_dt = datetime.fromtimestamp(
                                first_ms / 1000, tz=timezone.utc
                            )
                            last_dt = datetime.fromtimestamp(
                                last_ms / 1000, tz=timezone.utc
                            )
                            logger.info(f"First datetime: {first_dt.isoformat()}")
                            logger.info(f"Last datetime: {last_dt.isoformat()}")
                        except Exception as e:
                            logger.error(
                                f"Error converting timestamps to datetime: {e}"
                            )

                        # Calculate filter boundaries in milliseconds
                        start_ms = int(start_time.timestamp() * 1000)
                        end_ms = int(end_time.timestamp() * 1000)
                        logger.info(
                            f"Filtering for timestamps between {start_ms} ms and {end_ms} ms"
                        )

                        # Filter rows by timestamp in milliseconds
                        filtered_df = df[
                            (df["open_time_ms"] >= start_ms)
                            & (df["open_time_ms"] <= end_ms)
                        ].copy()  # Create an explicit copy
                        logger.info(
                            f"Filtered to {len(filtered_df)} rows in requested time range"
                        )

                        # Now convert timestamps to datetime objects
                        if len(filtered_df) > 0:
                            logger.info(
                                "Creating datetime objects for the filtered rows"
                            )
                            filtered_df.loc[:, "open_time"] = pd.to_datetime(
                                filtered_df["open_time_ms"], unit="ms"
                            )

                            # Append to result
                            all_data.append(filtered_df)
                        else:
                            logger.warning("No rows left after filtering")

                    # Clean up CSV file
                    if csv_path.exists():
                        csv_path.unlink()

            except Exception as e:
                logger.error(f"Error processing S3 download: {str(e)}", exc_info=True)

            # Clean up zip file
            if local_path.exists():
                local_path.unlink()

            # Move to next day
            current_date += timedelta(days=1)

    finally:
        # Clean up temp directory
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")

    # Combine all data
    if all_data:
        logger.info(f"Combining {len(all_data)} DataFrames")
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"Final result has {len(result)} rows")
        return result
    else:
        logger.warning("No data collected, returning empty DataFrame")
        return pd.DataFrame()


async def download_with_aioboto3(symbol, interval, start_time, end_time):
    """Download data using aioboto3 for S3 access.

    Args:
        symbol: Trading symbol
        interval: Time interval
        start_time: Start time for data
        end_time: End time for data

    Returns:
        Pandas DataFrame with data or None if download failed
    """
    # Apply nest_asyncio to allow running this async function in jupyter-like environments
    try:
        nest_asyncio.apply()
    except RuntimeError:
        # Already applied or not needed
        pass

    # Use current dates
    current_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)

    logger.info(f"Date range for aioboto3: {current_date.date()} to {end_date.date()}")
    logger.info(
        f"Start time: {start_time.isoformat()}, End time: {end_time.isoformat()}"
    )

    all_data = []
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create proper config object for aioboto3
        config = AioConfig(
            signature_version=botocore.UNSIGNED,  # Use unsigned requests for anonymous access
            region_name="us-east-1",
            connect_timeout=30,
            read_timeout=30,
        )

        # Create session
        session = aioboto3.Session()

        # Use client directly with anonymous access
        async with session.client("s3", config=config) as s3_client:
            while current_date <= end_date:
                # Format date for key
                date_str = current_date.strftime("%Y-%m-%d")

                # Determine file prefix
                if interval == "1s":
                    file_prefix = f"{symbol.upper()}-1s"
                else:
                    file_prefix = f"{symbol.upper()}-{interval}"

                # S3 key pattern - match Vision API pattern
                s3_key = f"data/spot/daily/klines/{symbol.upper()}/{interval}/{file_prefix}-{date_str}.zip"
                local_path = temp_dir / f"{file_prefix}-{date_str}.zip"

                try:
                    # Download using aioboto3 with anonymous access
                    logger.info(
                        f"Downloading with aioboto3: s3://public-binance-data/{s3_key}"
                    )

                    try:
                        # Use get_object with anonymous access
                        response = await s3_client.get_object(
                            Bucket="public-binance-data", Key=s3_key
                        )

                        # Read the body stream
                        body = await response["Body"].read()

                        # Write to local file
                        with open(local_path, "wb") as f:
                            f.write(body)

                        logger.info(
                            f"Successfully downloaded to {local_path} - size: {len(body)} bytes"
                        )

                        # Process the zip file
                        with zipfile.ZipFile(local_path, "r") as zip_ref:
                            file_list = zip_ref.namelist()
                            logger.info(f"Files in zip: {file_list}")

                            if not file_list:
                                logger.error("Zip file is empty")
                                current_date += timedelta(days=1)
                                continue

                            csv_file = file_list[0]
                            csv_path = temp_dir / csv_file
                            zip_ref.extract(csv_file, temp_dir)

                            # Read the CSV file
                            logger.info(f"Reading CSV file: {csv_path}")
                            df = pd.read_csv(csv_path)
                            logger.info(f"Read {len(df)} rows from CSV")

                            # Create column names for the dataframe
                            column_names = [
                                "open_time_us",  # Microsecond timestamp
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

                            # Rename columns
                            if len(df.columns) == len(column_names):
                                df.columns = column_names

                            # Convert microseconds to milliseconds for comparison
                            if len(df) > 0:
                                first_ts = df.iloc[
                                    0, 0
                                ]  # First timestamp in first column
                                last_ts = df.iloc[
                                    -1, 0
                                ]  # Last timestamp in first column
                                logger.info(f"First timestamp in file: {first_ts}")
                                logger.info(f"Last timestamp in file: {last_ts}")

                                # Use the standardized timestamp detection function
                                try:
                                    timestamp_unit = detect_timestamp_unit(first_ts)
                                    logger.info(
                                        f"Detected timestamp unit: {timestamp_unit}"
                                    )

                                    if timestamp_unit == "us":
                                        logger.info(
                                            "Timestamps are in microseconds, converting to milliseconds"
                                        )
                                        df["open_time_ms"] = df["open_time_us"] // 1000
                                    else:
                                        logger.info("Timestamps are in milliseconds")
                                        df["open_time_ms"] = df["open_time_us"]
                                except ValueError as e:
                                    logger.warning(
                                        f"Error detecting timestamp unit: {e}"
                                    )
                                    # Default to microseconds if detection fails (safer approach)
                                    logger.info(
                                        "Defaulting to microseconds, converting to milliseconds"
                                    )
                                    df["open_time_ms"] = df["open_time_us"] // 1000

                                # Convert to datetime for display of the first/last timestamps
                                try:
                                    first_ms = df["open_time_ms"].iloc[0]
                                    last_ms = df["open_time_ms"].iloc[-1]
                                    first_dt = datetime.fromtimestamp(
                                        first_ms / 1000, tz=timezone.utc
                                    )
                                    last_dt = datetime.fromtimestamp(
                                        last_ms / 1000, tz=timezone.utc
                                    )
                                    logger.info(
                                        f"First datetime: {first_dt.isoformat()}"
                                    )
                                    logger.info(f"Last datetime: {last_dt.isoformat()}")
                                except Exception as e:
                                    logger.error(
                                        f"Error converting timestamps to datetime: {e}"
                                    )

                                # Calculate filter boundaries in milliseconds
                                start_ms = int(start_time.timestamp() * 1000)
                                end_ms = int(end_time.timestamp() * 1000)
                                logger.info(
                                    f"Filtering for timestamps between {start_ms} ms and {end_ms} ms"
                                )

                                # Filter rows by timestamp in milliseconds
                                filtered_df = df[
                                    (df["open_time_ms"] >= start_ms)
                                    & (df["open_time_ms"] <= end_ms)
                                ].copy()  # Create an explicit copy
                                logger.info(
                                    f"Filtered to {len(filtered_df)} rows in requested time range"
                                )

                                # Now convert timestamps to datetime objects
                                if len(filtered_df) > 0:
                                    logger.info(
                                        "Creating datetime objects for the filtered rows"
                                    )
                                    filtered_df.loc[:, "open_time"] = pd.to_datetime(
                                        filtered_df["open_time_ms"], unit="ms"
                                    )

                                    # Append to result
                                    all_data.append(filtered_df)
                                else:
                                    logger.warning("No rows left after filtering")

                            # Clean up CSV file
                            if csv_path.exists():
                                csv_path.unlink()
                    except Exception as e:
                        logger.error(
                            f"Error downloading or processing file with S3 client: {str(e)}",
                            exc_info=True,
                        )

                except Exception as e:
                    logger.error(
                        f"Error with aioboto3 download: {str(e)}", exc_info=True
                    )

                # Clean up zip file
                if local_path.exists():
                    local_path.unlink()

                # Move to next day
                current_date += timedelta(days=1)

    except Exception as e:
        logger.error(f"Error in aioboto3 S3 session: {str(e)}", exc_info=True)

    finally:
        # Clean up temp directory
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")

    # Combine all data
    if all_data:
        logger.info(f"Combining {len(all_data)} DataFrames")
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"Final result has {len(result)} rows")
        return result
    else:
        logger.warning("No data collected, returning empty DataFrame")
        return pd.DataFrame()


def download_with_boto3(symbol, interval, start_time, end_time):
    """Download data using official boto3 for S3 access.

    Args:
        symbol: Trading symbol
        interval: Time interval
        start_time: Start time for data
        end_time: End time for data

    Returns:
        Pandas DataFrame with data or None if download failed
    """
    # Use current dates
    current_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = end_time.replace(hour=23, minute=59, second=59, microsecond=999999)

    logger.info(f"Date range for boto3: {current_date.date()} to {end_date.date()}")
    logger.info(
        f"Start time: {start_time.isoformat()}, End time: {end_time.isoformat()}"
    )

    all_data = []
    temp_dir = Path(tempfile.mkdtemp())

    try:
        # Create session with anonymous access configuration
        session = boto3.Session()
        s3_client = session.client(
            "s3",
            config=boto3.session.Config(
                signature_version=botocore.UNSIGNED,  # Use unsigned requests for anonymous access
                region_name="us-east-1",
                connect_timeout=30,
                read_timeout=30,
            ),
        )

        while current_date <= end_date:
            # Format date for key
            date_str = current_date.strftime("%Y-%m-%d")

            # Determine file prefix
            if interval == "1s":
                file_prefix = f"{symbol.upper()}-1s"
            else:
                file_prefix = f"{symbol.upper()}-{interval}"

            # Use direct Vision API URL instead of S3 bucket
            url = f"https://data.binance.vision/data/spot/daily/klines/{symbol.upper()}/{interval}/{file_prefix}-{date_str}.zip"
            local_path = temp_dir / f"{file_prefix}-{date_str}.zip"

            try:
                # Download directly from Binance Vision API using httpx
                logger.info(f"Downloading with boto3 (via httpx): {url}")

                # Use httpx for direct download
                with httpx.Client(timeout=30.0) as client:
                    response = client.get(url)
                    if response.status_code != 200:
                        logger.error(
                            f"Failed to download {url}: HTTP {response.status_code}"
                        )
                        current_date += timedelta(days=1)
                        continue

                    # Write to local file
                    with open(local_path, "wb") as f:
                        f.write(response.content)

                    logger.info(
                        f"Successfully downloaded to {local_path} - size: {len(response.content)} bytes"
                    )

                # Process the zip file (similar to other methods)
                with zipfile.ZipFile(local_path, "r") as zip_ref:
                    file_list = zip_ref.namelist()
                    logger.info(f"Files in zip: {file_list}")

                    if not file_list:
                        logger.error("Zip file is empty")
                        current_date += timedelta(days=1)
                        continue

                    csv_file = file_list[0]
                    csv_path = temp_dir / csv_file
                    zip_ref.extract(csv_file, temp_dir)

                    # Read the CSV file
                    logger.info(f"Reading CSV file: {csv_path}")
                    df = pd.read_csv(csv_path)
                    logger.info(f"Read {len(df)} rows from CSV")

                    # Create column names for the dataframe
                    column_names = [
                        "open_time_us",  # Microsecond timestamp
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

                    # Rename columns
                    if len(df.columns) == len(column_names):
                        df.columns = column_names

                    # Convert microseconds to milliseconds for comparison
                    if len(df) > 0:
                        first_ts = df.iloc[0, 0]  # First timestamp in first column
                        last_ts = df.iloc[-1, 0]  # Last timestamp in first column
                        logger.info(f"First timestamp in file: {first_ts}")
                        logger.info(f"Last timestamp in file: {last_ts}")

                        # Use the standardized timestamp detection function
                        try:
                            timestamp_unit = detect_timestamp_unit(first_ts)
                            logger.info(f"Detected timestamp unit: {timestamp_unit}")

                            if timestamp_unit == "us":
                                logger.info(
                                    "Timestamps are in microseconds, converting to milliseconds"
                                )
                                df["open_time_ms"] = df["open_time_us"] // 1000
                            else:
                                logger.info("Timestamps are in milliseconds")
                                df["open_time_ms"] = df["open_time_us"]
                        except ValueError as e:
                            logger.warning(f"Error detecting timestamp unit: {e}")
                            # Default to microseconds if detection fails (safer approach)
                            logger.info(
                                "Defaulting to microseconds, converting to milliseconds"
                            )
                            df["open_time_ms"] = df["open_time_us"] // 1000

                        # Convert to datetime for display of the first/last timestamps
                        try:
                            first_ms = df["open_time_ms"].iloc[0]
                            last_ms = df["open_time_ms"].iloc[-1]
                            first_dt = datetime.fromtimestamp(
                                first_ms / 1000, tz=timezone.utc
                            )
                            last_dt = datetime.fromtimestamp(
                                last_ms / 1000, tz=timezone.utc
                            )
                            logger.info(f"First datetime: {first_dt.isoformat()}")
                            logger.info(f"Last datetime: {last_dt.isoformat()}")
                        except Exception as e:
                            logger.error(
                                f"Error converting timestamps to datetime: {e}"
                            )

                        # Calculate filter boundaries in milliseconds
                        start_ms = int(start_time.timestamp() * 1000)
                        end_ms = int(end_time.timestamp() * 1000)
                        logger.info(
                            f"Filtering for timestamps between {start_ms} ms and {end_ms} ms"
                        )

                        # Filter rows by timestamp in milliseconds
                        filtered_df = df[
                            (df["open_time_ms"] >= start_ms)
                            & (df["open_time_ms"] <= end_ms)
                        ].copy()  # Create an explicit copy
                        logger.info(
                            f"Filtered to {len(filtered_df)} rows in requested time range"
                        )

                        # Now convert timestamps to datetime objects
                        if len(filtered_df) > 0:
                            logger.info(
                                "Creating datetime objects for the filtered rows"
                            )
                            filtered_df.loc[:, "open_time"] = pd.to_datetime(
                                filtered_df["open_time_ms"], unit="ms"
                            )

                            # Append to result
                            all_data.append(filtered_df)
                        else:
                            logger.warning("No rows left after filtering")

                    # Clean up CSV file
                    if csv_path.exists():
                        csv_path.unlink()

            except Exception as e:
                logger.error(f"Error with boto3 download: {str(e)}", exc_info=True)

            # Clean up zip file
            if local_path.exists():
                local_path.unlink()

            # Move to next day
            current_date += timedelta(days=1)

    except Exception as e:
        logger.error(f"Error in boto3 session: {str(e)}", exc_info=True)

    finally:
        # Clean up temp directory
        try:
            import shutil

            shutil.rmtree(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temp directory: {e}")

    # Combine all data
    if all_data:
        logger.info(f"Combining {len(all_data)} DataFrames")
        result = pd.concat(all_data, ignore_index=True)
        logger.info(f"Final result has {len(result)} rows")
        return result
    else:
        logger.warning("No data collected, returning empty DataFrame")
        return pd.DataFrame()


def run_single_download(args):
    """Run a single download test.

    Args:
        args: Tuple containing (download_method, symbol, interval, start_time, end_time, test_num, total_tests)

    Returns:
        Tuple of (elapsed_time, result_length)
    """
    download_method, symbol, interval, start_time, end_time, test_num, total_tests = (
        args
    )
    method_name = download_method.name.replace("_", " ").title()
    print(f"\nDownload test {test_num}/{total_tests} using {method_name}...")

    start = time.time()
    result = None

    try:
        if download_method == DownloadMethod.VISION_CLIENT:
            # First use a debug client to see what dates it's using
            from core.sync.vision_constraints import get_vision_url as client_get_url
            from core.sync.vision_constraints import FileType

            # Force logs from the VisionDataClient
            old_level = logger.level
            logger.setLevel("DEBUG")

            # Get an example URL for a snapshot day
            example_date = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
            market_type_str = "spot"  # Assuming spot market

            example_url = client_get_url(
                symbol=symbol,
                interval=interval,
                date=example_date,
                file_type=FileType.DATA,
                market_type=market_type_str,
            )

            logger.info(f"VisionDataClient would use URL like: {example_url}")

            # Debug the client initialization
            try:
                print("Creating VisionDataClient instance...")
                client = VisionDataClient(symbol, interval)
                print(f"  Symbol: {client.symbol}")
                print(f"  Interval: {client.interval}, type: {type(client.interval)}")
                print(
                    f"  Interval obj: {client.interval_obj}, type: {type(client.interval_obj)}"
                )
                print(
                    f"  Market type: {client.market_type}, type: {type(client.market_type)}"
                )
                print(
                    f"  Market type string: {client.market_type_str}, type: {type(client.market_type_str)}"
                )

                try:
                    logger.debug(
                        f"VisionDataClient fetching data from {start_time} to {end_time}"
                    )
                    result = client.fetch(start_time, end_time)
                    logger.debug(
                        f"VisionDataClient fetch completed with {len(result)} records"
                    )
                except Exception as e:
                    print(f"Error fetching data: {e}\n")
                    import traceback

                    traceback.print_exc()
                    print("\n")
            except Exception as e:
                print(f"Error creating client: {e}")

            # Create the client and get data
            finally:
                if "client" in locals() and client:
                    client.close()
                logger.setLevel(old_level)

        elif download_method in (
            DownloadMethod.HTTPX_CHROME,
            DownloadMethod.HTTPX_FIREFOX,
            DownloadMethod.HTTPX_SAFARI,
        ):
            user_agent = USER_AGENTS[download_method]
            result = download_with_httpx(
                symbol, interval, start_time, end_time, user_agent
            )

        elif download_method == DownloadMethod.AWS_CLI:
            result = download_with_aws_cli(symbol, interval, start_time, end_time)

        elif download_method == DownloadMethod.AIOBOTO3:
            # Run the async function in the event loop
            result = asyncio.run(
                download_with_aioboto3(symbol, interval, start_time, end_time)
            )

        elif download_method == DownloadMethod.BOTO3:
            # Use the synchronous boto3 implementation
            result = download_with_boto3(symbol, interval, start_time, end_time)

        else:
            raise ValueError(f"Unknown download method: {download_method}")

        elapsed = time.time() - start

        result_length = len(result) if result is not None else 0
        print(f"Download completed in {elapsed:.2f}s - got {result_length} records")
        return elapsed, result_length

    except Exception as e:
        elapsed = time.time() - start
        logger.error(f"Download failed after {elapsed:.2f}s: {e}")
        return elapsed, 0


def heartbeat_monitor(event, interval=5):
    """Display a heartbeat message periodically until signaled to stop.

    Args:
        event: Threading event to signal stopping
        interval: Time between heartbeats in seconds
    """
    iteration = 0
    while not event.is_set():
        iteration += 1
        print(
            f"[Heartbeat {iteration}] Still running... waiting for downloads to complete"
        )
        event.wait(interval)


def benchmark_vision_download(
    symbol="BTCUSDT",
    interval="1s",
    days_back=3,
    download_count=5,
    run_concurrent=False,
    max_workers=None,
    heartbeat_interval=5,
    download_methods=None,
):
    """Benchmark the VisionDataClient download performance.

    Args:
        symbol: Symbol to download data for
        interval: Time interval to download
        days_back: How many days back to fetch data
        download_count: Number of times to repeat the download for averaging
        run_concurrent: Whether to run downloads concurrently
        max_workers: Maximum number of concurrent workers (None for default)
        heartbeat_interval: Seconds between heartbeat messages
        download_methods: List of download methods to benchmark (default: all)
    """
    # Default to vision client if no methods specified
    if download_methods is None:
        download_methods = [DownloadMethod.VISION_CLIENT]

    print(f"Benchmarking download methods for {symbol} {interval} data")
    print(f"Testing each method {download_count} times for averaging")
    print(
        f"Download methods: {', '.join(m.name.replace('_', ' ').title() for m in download_methods)}"
    )
    print(f"Execution mode: {'Concurrent' if run_concurrent else 'Sequential'}")

    # Calculate the date range - using a small window for benchmarking
    end_time = enforce_utc_timezone(datetime.utcnow() - timedelta(days=days_back))
    start_time = end_time - timedelta(hours=6)  # 6-hour window

    print(f"Date range: {start_time.isoformat()} to {end_time.isoformat()}")

    # Results dictionary to store results by method
    results = {
        method: {"times": [], "avg": 0, "min": 0, "max": 0, "success": 0, "records": 0}
        for method in download_methods
    }

    # Prepare arguments for downloads
    download_args = []
    for method in download_methods:
        for i in range(download_count):
            download_args.append(
                (method, symbol, interval, start_time, end_time, i + 1, download_count)
            )

    if run_concurrent:
        # Set up heartbeat monitor
        stop_event = threading.Event()
        heartbeat_thread = threading.Thread(
            target=heartbeat_monitor, args=(stop_event, heartbeat_interval)
        )
        heartbeat_thread.daemon = True  # Make thread exit when main thread exits

        try:
            # Run downloads using ThreadPoolExecutor for concurrency
            futures = []
            heartbeat_thread.start()

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers
            ) as executor:
                # Submit all tasks and collect futures
                print("Starting concurrent downloads...")
                for args in download_args:
                    futures.append(executor.submit(run_single_download, args))

                # Wait for all futures to complete
                for future in concurrent.futures.as_completed(futures):
                    try:
                        elapsed, length = future.result()
                        method = download_args[futures.index(future)][0]

                        if length > 0:  # Only count successful downloads
                            results[method]["times"].append(elapsed)
                            results[method]["success"] += 1
                            results[method][
                                "records"
                            ] = length  # Store the most recent record count
                    except Exception as e:
                        logger.error(f"Task failed: {e}")
        finally:
            # Stop the heartbeat thread
            stop_event.set()
            heartbeat_thread.join(timeout=1.0)  # Wait for heartbeat thread to finish
            print("All downloads completed or failed")
    else:
        # Run downloads sequentially
        for args in download_args:
            elapsed, length = run_single_download(args)
            method = args[0]

            if length > 0:  # Only count successful downloads
                results[method]["times"].append(elapsed)
                results[method]["success"] += 1
                results[method][
                    "records"
                ] = length  # Store the most recent record count

    # Calculate statistics for each method
    for method, data in results.items():
        if data["times"]:
            data["avg"] = sum(data["times"]) / len(data["times"])
            data["min"] = min(data["times"])
            data["max"] = max(data["times"])

    # Display results
    print("\nBenchmark Results:")
    print("=" * 80)
    print(
        f"{'Method':<20} {'Avg Time':<10} {'Min Time':<10} {'Max Time':<10} {'Success':<10} {'Points/sec':<10}"
    )
    print("-" * 80)

    for method, data in results.items():
        method_name = method.name.replace("_", " ").title()
        avg_time = f"{data['avg']:.2f}s" if data["times"] else "N/A"
        min_time = f"{data['min']:.2f}s" if data["times"] else "N/A"
        max_time = f"{data['max']:.2f}s" if data["times"] else "N/A"
        success = f"{data['success']}/{download_count}"

        points_per_sec = "N/A"
        if data["times"] and data["records"] > 0:
            points_per_sec = f"{data['records'] / data['avg']:.2f}"

        print(
            f"{method_name:<20} {avg_time:<10} {min_time:<10} {max_time:<10} {success:<10} {points_per_sec:<10}"
        )

    print("=" * 80)

    # Save results to JSON file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = f"benchmark_results_{timestamp}.json"

    # Convert results to serializable format
    json_results = {
        "timestamp": datetime.now().isoformat(),
        "symbol": symbol,
        "interval": interval,
        "date_range": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
        },
        "methods": {
            method.name: {
                "times": data["times"],
                "avg_time": data["avg"],
                "min_time": data["min"],
                "max_time": data["max"],
                "success_rate": f"{data['success']}/{download_count}",
                "records": data["records"],
                "points_per_second": (
                    data["records"] / data["avg"]
                    if data["avg"] > 0 and data["records"] > 0
                    else 0
                ),
            }
            for method, data in results.items()
        },
    }

    with open(results_file, "w") as f:
        json.dump(json_results, f, indent=2)

    print(f"\nDetailed results saved to {results_file}")

    return results


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Benchmark Vision API downloads")
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Symbol to download (default: BTCUSDT)",
    )
    parser.add_argument(
        "--interval", type=str, default="1s", help="Interval to download (default: 1s)"
    )
    parser.add_argument(
        "--days-back", type=int, default=3, help="Days back from today (default: 3)"
    )
    parser.add_argument(
        "--count", type=int, default=5, help="Number of downloads to run (default: 5)"
    )
    parser.add_argument(
        "--concurrent", action="store_true", help="Run downloads concurrently"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Max workers for concurrent mode (default: auto)",
    )
    parser.add_argument(
        "--heartbeat",
        type=int,
        default=5,
        help="Heartbeat interval in seconds (default: 5)",
    )
    parser.add_argument(
        "--methods",
        type=str,
        default="vision_client",
        help="Comma-separated list of download methods to test (default: vision_client). "
        "Options: vision_client, httpx_chrome, httpx_firefox, httpx_safari, aws_cli, aioboto3, boto3, all",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    # Parse download methods
    method_map = {
        "vision_client": DownloadMethod.VISION_CLIENT,
        "httpx_chrome": DownloadMethod.HTTPX_CHROME,
        "httpx_firefox": DownloadMethod.HTTPX_FIREFOX,
        "httpx_safari": DownloadMethod.HTTPX_SAFARI,
        "aws_cli": DownloadMethod.AWS_CLI,
        "aioboto3": DownloadMethod.AIOBOTO3,
        "boto3": DownloadMethod.BOTO3,  # Added official boto3
        "all": None,  # Special case for all methods
    }

    methods = []
    if args.methods.lower() == "all":
        methods = list(DownloadMethod)
    else:
        for method_str in args.methods.lower().split(","):
            method_str = method_str.strip()
            if method_str in method_map:
                methods.append(method_map[method_str])
            else:
                print(f"Warning: Unknown method '{method_str}', ignoring")

    if not methods:
        methods = [DownloadMethod.VISION_CLIENT]  # Default to vision client

    benchmark_vision_download(
        symbol=args.symbol,
        interval=args.interval,
        days_back=args.days_back,
        download_count=args.count,
        run_concurrent=args.concurrent,
        max_workers=args.workers,
        heartbeat_interval=args.heartbeat,
        download_methods=methods,
    )
