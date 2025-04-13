#!/usr/bin/env python
"""Common DataFrame class types and extensions for the data services.

This module centralizes custom DataFrame types and extensions used throughout
the data services. These types are designed to enforce specific constraints
and behaviors for consistent data handling.
"""

import pandas as pd
import traceback
from typing import Optional

from utils.config import CANONICAL_INDEX_NAME, DEFAULT_TIMEZONE
from utils.logger_setup import logger


class TimestampedDataFrame(pd.DataFrame):
    """DataFrame with enforced UTC timestamp index.

    This class enforces:
    1. Index must be DatetimeIndex
    2. Index must be timezone-aware and in UTC
    3. Index must be named 'open_time'
    4. Index must be monotonically increasing
    5. No duplicate indices allowed
    """

    def __init__(self, *args, **kwargs):
        """Initialize with DataFrame validation."""
        # Check if open_time exists as both index and column in the input DataFrame
        if args and isinstance(args[0], pd.DataFrame):
            df = args[0]
            # Add detailed debug logging
            logger.debug(
                f"Initializing TimestampedDataFrame with columns: {list(df.columns)}"
            )
            logger.debug(f"Input DataFrame index name: {df.index.name}")
            logger.debug(f"Input DataFrame index type: {type(df.index)}")

            if (
                hasattr(df, "index")
                and hasattr(df.index, "name")
                and df.index.name == CANONICAL_INDEX_NAME
                and CANONICAL_INDEX_NAME in df.columns
            ):
                # Create a new DataFrame without the ambiguous structure
                # Keep only the column version of open_time and set it as index later
                df = pd.DataFrame(df.reset_index())
                # Update args with the corrected DataFrame
                args = (df,) + args[1:]
                logger.debug("Resolved ambiguous open_time in index and columns")

        super().__init__(*args, **kwargs)
        self._validate_and_normalize_index()

        # After initialization, ensure open_time is available as a column
        # This is critical for compatibility with standard pandas operations
        if "open_time" not in self.columns:
            if hasattr(self.index, "name") and self.index.name == "open_time":
                logger.debug("Ensuring open_time exists as column (copied from index)")
                self["open_time"] = self.index
                logger.debug(
                    f"Added open_time column, dtype: {self['open_time'].dtype}"
                )

    def _validate_and_normalize_index(self):
        """Validate and normalize the index to meet requirements."""
        # Import here to avoid circular imports
        from utils.dataframe_utils import ensure_open_time_as_index

        try:
            # Use the centralized utility to ensure the index is properly set
            df_with_proper_index = ensure_open_time_as_index(self)

            # Since we can't replace self entirely, we need to update its properties
            if not self.equals(df_with_proper_index):
                logger.debug("Updating TimestampedDataFrame with normalized index")
                # Copy the index from the properly indexed DataFrame
                self.index = df_with_proper_index.index

                # Make sure columns match as well if they've changed
                if set(self.columns) != set(df_with_proper_index.columns):
                    for col in df_with_proper_index.columns:
                        if col not in self.columns:
                            self[col] = df_with_proper_index[col]

            # Log final state
            logger.debug(
                f"TimestampedDataFrame index properly validated: {len(self)} rows"
            )
        except Exception as e:
            logger.error(f"Error normalizing index: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise

    def to_pandas(self) -> pd.DataFrame:
        """Convert to standard pandas DataFrame with open_time as a column.

        This ensures the DataFrame can be used in contexts where open_time
        is expected to be a column, not just an index.

        Returns:
            A standard pandas DataFrame with open_time as a column
        """
        # Import here to avoid circular imports
        from utils.dataframe_utils import ensure_open_time_as_column

        # Create a copy to avoid modifying the original
        df = pd.DataFrame(self.copy())

        # Use the centralized utility to ensure open_time is properly handled as a column
        df = ensure_open_time_as_column(df)

        logger.debug(f"Converted to pandas DataFrame with columns: {list(df.columns)}")
        return df

    def __setitem__(self, key, value):
        """Override to prevent modification of index."""
        if key == CANONICAL_INDEX_NAME:
            logger.warning(
                f"Setting {CANONICAL_INDEX_NAME} directly - this may cause issues. Use index operations instead."
            )
        super().__setitem__(key, value)
