#!/usr/bin/env python
"""Utility module for handling time alignment and incomplete bars.

Key behaviors:
1. All units smaller than the interval are removed (e.g., for 1m, all seconds and microseconds are removed)
2. The current incomplete interval is removed for safety
3. Start times are rounded UP to next interval boundary if they have sub-interval units
   (e.g., 08:37:25.528448 gets rounded UP to 08:37:26.000000 for 1-second intervals)
4. End times are rounded DOWN to current interval boundary
   (e.g., 08:37:30.056345 gets rounded DOWN to 08:37:30.000000 for 1-second intervals)
5. Both start and end timestamps are INCLUSIVE on exact interval boundaries
6. Each bar has a duration of (interval - 1 microsecond)

Example:
For a time window from 2025-03-17 08:37:25.528448 to 2025-03-17 08:37:30.056345 with 1-second intervals:
- Adjusted start: 2025-03-17 08:37:26.000000 (rounded UP from 25.528448)
- Adjusted end: 2025-03-17 08:37:30.000000 (rounded DOWN from 30.056345)
- Expected records: 5 (seconds 26, 27, 28, 29, 30 inclusive)

IMPORTANT: When counting expected records for a time range:
1. Both boundaries are inclusive
2. Start times with microseconds are rounded UP to the next full second
3. End times with microseconds are rounded DOWN to the current second
4. For 1-second intervals with microseconds in timestamps, expected records may be fewer than naively calculated
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List
import re

from utils.logger_setup import get_logger
from utils.market_constraints import Interval

logger = get_logger(__name__, "INFO", show_path=False, rich_tracebacks=True)


@dataclass(frozen=True)
class TimeUnit:
    """Represents a time unit with conversion to microseconds."""

    name: str
    micros: int
    symbol: str

    @classmethod
    def MICRO(cls) -> "TimeUnit":
        return cls("microsecond", 1, "us")

    @classmethod
    def MILLI(cls) -> "TimeUnit":
        return cls("millisecond", 1_000, "ms")

    @classmethod
    def SECOND(cls) -> "TimeUnit":
        return cls("second", 1_000_000, "s")

    @classmethod
    def MINUTE(cls) -> "TimeUnit":
        return cls("minute", 60 * 1_000_000, "m")

    @classmethod
    def HOUR(cls) -> "TimeUnit":
        return cls("hour", 3600 * 1_000_000, "h")

    @classmethod
    def DAY(cls) -> "TimeUnit":
        return cls("day", 86400 * 1_000_000, "d")

    @classmethod
    def WEEK(cls) -> "TimeUnit":
        return cls("week", 7 * 86400 * 1_000_000, "w")

    @classmethod
    def get_all_units(cls) -> List["TimeUnit"]:
        """Get all available units in descending order of size."""
        return [
            cls.WEEK(),
            cls.DAY(),
            cls.HOUR(),
            cls.MINUTE(),
            cls.SECOND(),
            cls.MILLI(),
            cls.MICRO(),
        ]


def get_interval_micros(interval: Interval) -> int:
    """Convert interval to microseconds.

    Args:
        interval: The interval specification

    Returns:
        int: Interval duration in microseconds
    """
    # Parse interval value and unit
    match = re.match(r"(\d+)([a-zA-Z]+)", interval.value)
    if not match:
        raise ValueError(f"Invalid interval format: {interval.value}")

    value, unit_symbol = match.groups()
    value = int(value)

    # Find matching unit
    unit = next((u for u in TimeUnit.get_all_units() if u.symbol == unit_symbol), None)
    if unit is None:
        raise ValueError(f"Unknown unit symbol: {unit_symbol}")

    return value * unit.micros


def get_interval_timedelta(interval: Interval) -> timedelta:
    """Convert interval to timedelta.

    Args:
        interval: The interval specification

    Returns:
        timedelta: Interval duration
    """
    return timedelta(microseconds=get_interval_micros(interval))


def get_smaller_units(interval: Interval) -> List[TimeUnit]:
    """Get all units smaller than this interval.

    Args:
        interval: The interval specification

    Returns:
        List[TimeUnit]: Units smaller than the interval
    """
    interval_micros = get_interval_micros(interval)
    return [unit for unit in TimeUnit.get_all_units() if unit.micros < interval_micros]


def get_interval_floor(timestamp: datetime, interval: Interval) -> datetime:
    """Floor timestamp to interval boundary, removing all smaller units.

    Args:
        timestamp: The timestamp to floor
        interval: The interval specification

    Returns:
        datetime: Floor time with sub-interval units removed
    """
    interval_micros = get_interval_micros(interval)
    timestamp_micros = int(timestamp.timestamp() * 1_000_000)
    floored_micros = (timestamp_micros // interval_micros) * interval_micros
    return datetime.fromtimestamp(floored_micros / 1_000_000, timezone.utc)


def get_interval_ceiling(timestamp: datetime, interval: Interval) -> datetime:
    """Ceil timestamp to next interval boundary.

    Args:
        timestamp: The timestamp to ceiling
        interval: The interval specification

    Returns:
        datetime: Ceiling time (next interval with sub-interval units removed)
    """
    floor = get_interval_floor(timestamp, interval)
    if timestamp == floor:
        return floor
    return floor + get_interval_timedelta(interval)


def get_bar_close_time(open_time: datetime, interval: Interval) -> datetime:
    """Get the close time for a bar given its open time.

    Args:
        open_time: The bar's open time
        interval: The interval specification

    Returns:
        datetime: Close time (interval - 1 microsecond after open time)
    """
    logger.debug("\n=== Bar Close Time Calculation ===")
    logger.debug(f"Input open_time: {open_time}")
    logger.debug(f"Input interval: {interval}")

    interval_delta = get_interval_timedelta(interval)
    logger.debug(f"Interval timedelta: {interval_delta}")

    close_time = open_time + interval_delta - timedelta(microseconds=1)
    logger.debug(f"Calculated close_time: {close_time}")
    logger.debug(f"Close time microseconds: {close_time.microsecond}")

    return close_time


def adjust_time_window(
    start_time: datetime,
    end_time: datetime,
    interval: Interval,
    current_time: Optional[datetime] = None,
) -> Tuple[datetime, datetime]:
    """Adjust time window for data retrieval.

    Key behaviors:
    1. All units smaller than the interval are removed
    2. The current incomplete interval is removed for safety
    3. Start times are rounded UP to next interval if they have sub-interval units
    4. End times are rounded DOWN to current interval
    5. Both start and end timestamps are inclusive on interval boundaries

    Args:
        start_time: Start time
        end_time: End time
        interval: The interval specification
        current_time: Optional current time for testing

    Returns:
        Tuple of adjusted start and end times
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)

    # Ensure UTC timezone
    start_time = start_time.astimezone(timezone.utc)
    end_time = end_time.astimezone(timezone.utc)
    current_time = current_time.astimezone(timezone.utc)

    # Get floor times
    start_floor = get_interval_floor(start_time, interval)
    end_floor = get_interval_floor(end_time, interval)

    # For start time: round UP if there are any sub-interval units
    adjusted_start = (
        get_interval_ceiling(start_time, interval)
        if start_time > start_floor
        else start_floor
    )

    # For end time: check if we're in an incomplete interval
    interval_td = get_interval_timedelta(interval)
    time_since_floor = current_time - end_floor
    if time_since_floor < interval_td:
        # We're in an incomplete interval, move back one interval
        end_floor = end_floor - interval_td

    # Set end time to end of the interval (minus 1 microsecond)
    adjusted_end = get_bar_close_time(end_floor, interval)

    # Log adjustments if they were made
    if adjusted_start != start_time or adjusted_end != end_time:
        logger.debug(
            "Time window adjusted:"
            f"\nOriginal:  {start_time.isoformat()} -> {end_time.isoformat()}"
            f"\nAdjusted:  {adjusted_start.isoformat()} -> {adjusted_end.isoformat()}"
        )

    # Calculate and log the expected number of records
    if interval == Interval.SECOND_1:
        # For 1-second intervals, calculate seconds difference + 1 (inclusive boundaries)
        seconds_diff = int((adjusted_end - adjusted_start).total_seconds())
        expected_records = seconds_diff + 1  # Add 1 for inclusive boundaries
        logger.debug(f"Expected records with inclusive boundaries: {expected_records}")
        logger.debug(f"Time span in seconds: {seconds_diff} seconds")
        logger.debug(f"Boundaries: Both start and end timestamps are INCLUSIVE")

    return adjusted_start, adjusted_end


def is_bar_complete(
    bar_time: datetime, current_time: datetime, interval: Interval = Interval.SECOND_1
) -> bool:
    """Check if a bar is complete based on its timestamp.

    A bar is considered complete when:
    1. It's at least one interval old
    2. The bar's close time has passed

    Args:
        bar_time: The bar's open time
        current_time: Current time to compare against
        interval: The interval specification (default: 1 second)

    Returns:
        bool: True if the bar is complete, False otherwise
    """
    # Ensure UTC timezone
    bar_time = bar_time.astimezone(timezone.utc)
    current_time = current_time.astimezone(timezone.utc)

    # Get the bar's close time
    close_time = get_bar_close_time(bar_time, interval)

    # Bar is complete if we're past its close time
    return current_time > close_time
