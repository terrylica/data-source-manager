# Roadmap: Revamping Time Alignment Strategy (Prioritized Validation)

**Goal**: To align the time handling of the Vision API and cache with the Binance REST API's inherent boundary handling, as documented in `docs/api/binance_rest_api_boundary_behaviour.md`. We will prioritize building and testing a new validation class that is directly aligned with Binance REST API behavior before proceeding with broader code refactoring. This will ensure a solid foundation for time handling, adhering to the principles of real-world testing and avoiding mocks as per `docs/utilities_and_standards/pytest-construction.md`.

**Clarification on Time Alignment**:

It's crucial to understand that the goal is **not to remove time alignment entirely**, but to **shift the responsibility for alignment**. We aim to:\*\*

- **Eliminate manual time alignment logic when calling the Binance REST API directly.** We should rely on the REST API's documented boundary behavior. Any current manual alignment applied _before_ calling the REST API should be removed.
- **Implement manual time alignment for the Vision API and cache operations to _match_ the Binance REST API's behavior.** This ensures consistency across data sources and caching mechanisms. The `ApiBoundaryValidator` will be key to verifying this alignment.
- **Verify all alignment logic through integration tests against the Binance REST API.** This ensures our manual alignment for Vision API and cache accurately mirrors the REST API's behavior.

**Overall Strategy (Prioritized Validation)**:

1. **Create and Test `ApiBoundaryValidator`**: Develop a new class, `ApiBoundaryValidator` in `utils/api_boundary_validator.py`, specifically designed to validate time boundaries and data ranges against the Binance REST API. Thoroughly test this class by directly comparing its validation outcomes with actual Binance REST API responses for various scenarios. **This aligns with the `docs/utilities_and_standards/pytest-construction.md` rule of using real-world data and integration tests, avoiding mocks and sample data.** This validator will be used to ensure our manual alignment logic is correct.

2. **Refactor Validation Modules**: Once `ApiBoundaryValidator` is robust and fully tested, refactor `utils/validation.py` and `utils/cache_validator.py` to utilize this new class for all time-related validations. Replace the old manual alignment-based validation logic with methods from `ApiBoundaryValidator`.

3. **Identify and Analyze Time Alignment Logic**: After establishing the new validation foundation, proceed to thoroughly review the codebase to pinpoint all instances where time alignment or manipulation is currently performed, especially in `utils/time_alignment.py`, `core/data_source_manager.py`, `core/market_data_client.py`, `core/vision_data_client.py`, and `core/cache_manager.py`. **Focus on distinguishing between manual alignment for REST API calls (which should be removed) and manual alignment for Vision API/cache (which should be verified against REST API behavior).**

4. **Remove Manual Alignment for REST API Calls**: Systematically remove the identified time alignment logic that is applied _before_ making calls to the Binance REST API. Ensure that timestamps are passed to REST API clients as they are initially provided by the user, relying on the API to handle boundaries.

5. **Refactor Vision API and Cache Alignment**: Adapt the Vision API data retrieval and cache management logic in `core/vision_data_client.py` and `core/cache_manager.py` to implement manual time alignment that **mirrors the Binance REST API's boundary behavior**. Use the `ApiBoundaryValidator` to guide and verify this manual alignment.

6. **Testing and Verification (Full System)**: Implement comprehensive system-level tests to verify that the revamped codebase, with the new validation and adjusted alignment, correctly handles time boundaries, data retrieval, and caching in full alignment with the Binance REST API's documented behavior. **All tests will be integration tests against the real Binance API, as per `docs/utilities_and_standards/pytest-construction.md`. Crucially, tests should verify that the manual alignment in Vision API and cache is consistent with REST API behavior.**

**Step-by-Step Plan (File by File - Prioritized Validation):**

## Phase 1: Build and Test `ApiBoundaryValidator`

1. **`utils/api_boundary_validator.py` (NEW FILE)**:

   - **Action**: Create a new file `utils/api_boundary_validator.py`. Define the `ApiBoundaryValidator` class with methods to:
     - `__init__(self, market_type: MarketType = MarketType.SPOT)`: Initialize with market type and potentially an HTTP client.
     - `is_valid_time_range(self, start_time: datetime, end_time: datetime, interval: Interval) -> bool`: Validate if the given time range and interval are valid according to Binance API boundaries. This method will internally call Binance API to check.
     - `get_api_boundaries(self, start_time: datetime, end_time: datetime, interval: Interval) -> Dict`: Call Binance API and analyze the response to determine the actual start and end times of the data returned by the API for the given parameters. Return a dictionary containing API-aligned boundaries.
     - `does_data_range_match_api_response(self, df: pd.DataFrame, start_time: datetime, end_time: datetime, interval: Interval) -> bool`: Validate if a given DataFrame's time range matches what is expected from the Binance API for the specified start time, end time, and interval.
   - **Outcome**: A new `ApiBoundaryValidator` class ready for testing.

2. **`tests/api_boundary/test_api_boundary_validator.py` (MOVED AND UPDATED FILE)**:
   - **Action**: Move the test file to `tests/api_boundary/test_api_boundary_validator.py`. Write comprehensive unit tests for `ApiBoundaryValidator` methods. **Crucially, and in adherence to `docs/utilities_and_standards/pytest-construction.md`, each test should:**
     - Instantiate `ApiBoundaryValidator`.
     - Define test start time, end time, and interval.
     - **Make a direct call to Binance REST API (e.g., `/api/v3/klines`) using `httpx` or `aiohttp` within the test to get real-world API responses. This is crucial for integration testing and avoiding mocks.**
     - Call the `ApiBoundaryValidator` method being tested (e.g., `is_valid_time_range`, `get_api_boundaries`).
     - **Assert that the result from `ApiBoundaryValidator` _exactly matches_ the behavior observed from the Binance REST API response. This ensures the validator is truly aligned with the API.** Test various scenarios:
       - Exact boundaries, millisecond precision, cross-day/month/year, different intervals, time ranges relative to "now", and edge cases as documented in `docs/api/binance_rest_api_boundary_behaviour.md`.
     - **Utilize `caplog` and `utils/logger_setup.py` for logging and debugging within tests, as recommended by `docs/utilities_and_standards/pytest-construction.md`.**
     - **Ensure proper resource initialization and cleanup, especially for HTTP client sessions used in tests, aligning with `docs/utilities_and_standards/pytest-construction.md`.**
     - **If using `pytest-asyncio`, verify that `asyncio_default_fixture_loop_scope = function` is configured to prevent deprecation warnings and ensure consistent event loop behavior, as per `docs/utilities_and_standards/pytest-construction.md`.**
   - **Outcome**: Fully tested and validated `ApiBoundaryValidator` class that accurately reflects Binance API time boundary behavior through real integration tests.

## Phase 2: Refactor Validation Modules to Use `ApiBoundaryValidator`

1. **`utils/validation.py`**:

   - **Action**: Refactor `DataValidation` class.
     - **Deprecate/Remove**: `validate_time_boundaries`.
     - **Integrate `ApiBoundaryValidator`**: Use `ApiBoundaryValidator` within `DataValidation` to perform time range and boundary validations. Potentially add new methods to `DataValidation` that leverage `ApiBoundaryValidator`. **Ensure that `DataValidation` is initialized with an instance of `ApiBoundaryValidator` to enable its functionality.**
   - **Code Change**:

   ````diff
   ```language:utils/validation.py
   // ... existing code ...
   class DataValidation:
       def __init__(self, api_boundary_validator: ApiBoundaryValidator): # Inject ApiBoundaryValidator
           self.api_boundary_validator = api_boundary_validator

       # @staticmethod - REMOVE validate_time_boundaries entirely
       # def validate_time_boundaries( ... ): ...

       @staticmethod
       def validate_time_window(start_time: datetime, end_time: datetime) -> None:
           if start_time >= end_time:
               raise ValidationError("Start time must be before end time.")
           time_diff = end_time - start_time
           if time_diff > MAX_TIME_RANGE:
               raise ValidationError(f"Time range exceeds maximum allowed: {MAX_TIME_RANGE}")

       # Example of a new validation method using ApiBoundaryValidator
       def validate_api_time_range(self, start_time: datetime, end_time: datetime, interval: str) -> bool:
           """Validates time range against Binance API boundaries using ApiBoundaryValidator."""
           interval_enum = Interval(interval) # Ensure Interval enum is used
           return self.api_boundary_validator.is_valid_time_range(start_time, end_time, interval_enum)

   // ... existing code ...

   # In factory or initialization code where DataValidation is created:
   # api_boundary_validator = ApiBoundaryValidator()
   # data_validator = DataValidation(api_boundary_validator) # Inject instance
   ```
   ````

2. **`utils/cache_validator.py`**:

   - **Action**: Refactor `CacheValidator` class.
     - **Review**: Examine `validate_cache_data` and `validate_cache_integrity` to see if any time-alignment specific validations are present. If so, replace them with calls to `ApiBoundaryValidator`.
     - **Integrate `ApiBoundaryValidator`**: If needed, use `ApiBoundaryValidator` to validate cached data time ranges against API behavior. **Ensure `CacheValidator` can receive and utilize an `ApiBoundaryValidator` instance when needed.**
   - **Code Change**:

   ````diff
   ```language:utils/cache_validator.py
   // ... existing code ...
   class CacheValidator:
       # ...

       @classmethod
       def validate_cache_data(
           cls, df: pd.DataFrame, allow_empty: bool = False, api_boundary_validator: ApiBoundaryValidator = None # Inject validator if needed
       ) -> Optional[CacheValidationError]:
           """Validate cached data DataFrame. - Use ApiBoundaryValidator if needed"""
           # ... existing validations ...

           # Example of using ApiBoundaryValidator for data range validation (if needed)
           # if api_boundary_validator:
           #     is_api_aligned = api_boundary_validator.does_data_range_match_api_response(df, expected_start_time, expected_end_time, interval)
           #     if not is_api_aligned:
           #         return CacheValidationError(...)

           return None

       # ...
   ```
   ````

3. **`tests/test_validation.py` and `tests/api_boundary/test_api_boundary_validator.py`**:
   - **Action**:
     - **Run existing tests**: Execute existing tests for `validation.py` and `cache_validator.py` to ensure refactoring hasn't introduced regressions.
     - **Add new tests**: Add new test cases specifically to test the integration of `ApiBoundaryValidator` in `validation.py` and `cache_validator.py`. Focus on testing the new validation methods that utilize `ApiBoundaryValidator`. **These tests should also be integration tests, verifying the validation logic against the real Binance API through `ApiBoundaryValidator`.**
   - **Outcome**: Validation modules refactored to use `ApiBoundaryValidator` and confirmed to be working correctly through tests.

## Phase 3: Identify and Analyze Time Alignment Logic (and subsequent phases from original roadmap)

1. **`utils/time_alignment.py`**:

   - **Action**: In-depth analysis of all functions in this module. Understand their purpose and how they are used for time manipulation and alignment. **Specifically, identify and categorize functions into:**
     - **Functions to Deprecate/Remove**: Functions that are purely for Binance API time alignment and will become obsolete _for REST API calls_. (e.g., `adjust_time_window`, `get_interval_floor`, `get_interval_ceiling`, potentially `get_time_boundaries` and `filter_time_range` if they are heavily reliant on the old alignment logic and used for REST API).
     - **Functions to Retain/Repurpose**: Functions that might still be useful for general time utility, independent of Binance API alignment (e.g., `get_interval_micros`, `get_interval_timedelta`, `is_bar_complete`, `enforce_utc_timezone`). These might need renaming to reflect their general utility. **Also, identify functions that might be adapted for manual alignment of Vision API and cache to match REST API behavior.**
   - **Outcome**: List of functions to be deprecated or removed. Clear understanding of which functions to keep and potentially repurpose. Identification of functions for potential adaptation for Vision API/cache alignment.

2. **`core/data_source_manager.py`**:

   - **Action**: Trace how `TimeRangeManager` and time alignment functions are used within `get_data` and `_fetch_from_source` methods. Identify where start and end times are adjusted **before API calls and cache operations**. **Focus on the `get_time_boundaries` and `filter_dataframe` usage within `get_data`. Determine if these are used for REST API calls and should be removed, or if they are used for Vision API/cache and need to be adapted for REST API-like alignment.**
   - **Outcome**: Mark code sections for removal related to time alignment _for REST API calls_. Understand the data flow and dependencies on time alignment. **Note the interaction with `TimeRangeManager.get_time_boundaries` and how the returned adjusted times are used, and for which data source.**

3. **`core/market_data_client.py`**:

   - **Action**: Examine the `fetch` method and related helper functions (`_calculate_chunks`, `_validate_request_params`) to see if any time manipulations are performed **before constructing REST API requests**. **Specifically, check `_calculate_chunks` to see if chunking logic is dependent on any time alignment assumptions that should be removed.** Also, review `_validate_request_params` for time parameter validation and remove any alignment-specific checks related to REST API calls.
   - **Outcome**: Identify and mark any time alignment code for removal _related to REST API calls_. Confirm that time parameters are passed to the REST API as is. **Ensure chunk calculation and request parameter validation are time-alignment agnostic for REST API.**

4. **`core/vision_data_client.py`**:

   - **Action**: Analyze `fetch` and `_download_and_cache` methods. Investigate how time boundaries are handled for Vision API data retrieval and caching. Check interactions with `vision_constraints.py`. **Pay attention to how `_get_cache_path` is constructed and if it relies on aligned times. Determine if manual alignment is needed here to match REST API behavior.** Also, review `_validate_cache` to see if cache validation is tied to specific time alignments and how to adapt it to align with REST API behavior.
   - **Outcome**: Identify time alignment logic to be adapted or added _for Vision API and cache to match REST API behavior_. Understand how caching is currently time-dependent and how to adapt it. **Determine if cache paths and validation need adjustments to achieve REST API-like alignment.**

5. **`core/cache_manager.py`**:
   - **Action**: Review `save_to_cache`, `load_from_cache`, `get_cache_path`, and `get_cache_key` methods. Understand how cache keys are generated based on date and interval, and how time is used in cache metadata. **Analyze `get_cache_path` and `get_cache_key` to see if they are using date manipulations that need to be adjusted to align with REST API behavior.** Also, check if `save_to_cache` and `load_from_cache` are implicitly relying on aligned times and how to adapt them for REST API-like alignment.
   - **Outcome**: Determine how to adjust cache key generation and retrieval to align with the API's time boundaries without manual alignment _for REST API calls, but potentially with manual alignment for cache itself to mimic REST API behavior_. **Decide if cache key structure needs simplification or adjustment to achieve REST API-like alignment.**

## Phase 4: Code Modification and Refactoring (and subsequent phases from original roadmap)

1. **`utils/time_alignment.py`**:

   - **Action**: Deprecate or remove functions identified in Phase 3, Step 1 as "Functions to Deprecate/Remove" _that are used for REST API calls_. For "Functions to Retain/Repurpose", rename them to have a more general utility context (e.g., `enforce_utc_timezone` is fine, but something like `adjust_time_window` should be removed or adapted for Vision API/cache alignment). **Adapt functions as needed to implement manual alignment for Vision API and cache to match REST API behavior, verified by `ApiBoundaryValidator`.**
   - **Code Change**:

   ````diff
   ```language:utils/time_alignment.py
   // existing code ...
   {{ Deprecate or remove functions identified for removal *related to REST API calls*. For example: }}
   # DEPRECATED: No longer used for Binance REST API time alignment
   # def adjust_time_window(...):
   #     ...
   #     return adjusted_start, adjusted_end

   {{ For functions to retain, ensure they are clearly for general time utility: }}
   class TimeRangeManager:
       @staticmethod
       def enforce_utc_timezone(dt: datetime) -> datetime:
           """Ensures datetime object is timezone aware and in UTC."""
           if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
               return dt.replace(tzinfo=timezone.utc)
           return dt.astimezone(timezone.utc)
   // ... existing code ...
   ```
   ````

2. **`core/data_source_manager.py`**:

   - **Action**: Remove the marked time alignment code sections in `get_data` and `_fetch_from_source` _that are used for REST API calls_. **Specifically, remove calls to `TimeRangeManager.get_time_boundaries` and `TimeRangeManager.filter_dataframe` or adapt their usage if they are intended for Vision API/cache alignment.** Ensure that start and end times are used as provided by the user when calling REST API clients and cache manager.
   - **Code Change**:

   ````diff
   ```language:core/data_source_manager.py
   // ... existing code ...
   async def get_data(
       self,
       symbol: str,
       start_time: datetime,
       end_time: datetime,
       interval: Interval = Interval.SECOND_1,
       use_cache: bool = True,
       enforce_source: DataSource = DataSource.AUTO,
   ) -> pd.DataFrame:
       // ... existing code ...

       # Get time boundaries using the centralized manager - REMOVE THIS SECTION *for REST API calls*
       # time_boundaries = TimeRangeManager.get_time_boundaries(
       #     start_time, end_time, interval
       # )
       # start_time = time_boundaries["adjusted_start"]
       # end_time = time_boundaries["adjusted_end"]

       logger.info(
           f"Using time boundaries: {start_time} -> {end_time} (exclusive end)"
       )
       # logger.debug(f"Expected records: {time_boundaries['expected_records']}") - REMOVE THIS LINE

       // ... existing code ...
       if is_valid:
           cached_data = await self.cache_manager.load_from_cache(
               symbol=symbol, interval=interval.value, date=start_time
           )
           if cached_data is not None:
               # Use centralized time filtering function via manager - REMOVE OR ADAPT IF NEEDED *depending on if cache needs manual alignment*
               # cached_data = TimeRangeManager.filter_dataframe(
               #     cached_data, start_time, end_time
               # )
               if not cached_data.empty:
                   self._cache_stats["hits"] += 1
                   logger.info(f"Cache hit for {symbol} from {start_time}")
                   return cached_data
       // ... existing code ...
       df = await self._fetch_from_source(
           symbol, start_time, end_time, interval, use_vision
       )
       // ... existing code ...
   ```
   ````

3. **`core/market_data_client.py`**:

   - **Action**: Remove any identified time alignment logic from `fetch` and related methods _related to REST API calls_. **In `_calculate_chunks`, ensure chunk boundaries are calculated based on `CHUNK_SIZE` and the provided `start_ms` and `end_ms` without any interval-based adjustments that are no longer needed for REST API.** In `_validate_request_params`, review time parameter validations and remove any alignment-specific checks if present _for REST API calls_.
   - **Code Change**:

   ````diff
   ```language:core/market_data_client.py
   // ... existing code ...
   def _calculate_chunks(
       self, start_ms: int, end_ms: int, interval: Interval
   ) -> List[Tuple[int, int]]:
       """Calculate chunk ranges based on start and end times."""
       chunks = []
       current_start = start_ms
       while current_start < end_ms:
           chunk_end = min(current_start + self.CHUNK_SIZE_MS - 1, end_ms) # Ensure chunk_end does not exceed end_ms
           chunks.append((current_start, chunk_end))
           current_start = chunk_end + 1 # Move current_start to the next millisecond after chunk_end
       return chunks
   // ... existing code ...
   def _validate_request_params(
       self, symbol: str, interval: Interval, start_time: datetime, end_time: datetime
   ) -> None:
       """Validate request parameters."""
       if not symbol:
           raise ValueError("Symbol must be provided.")
       if not isinstance(interval, Interval):
           raise TypeError("Interval must be an Interval enum.")
       if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
           raise TypeError("Start and end times must be datetime objects.")
       if start_time >= end_time:
           raise ValueError("Start time must be before end time.")
       # Remove any alignment specific validations here if present *related to REST API calls*
       # Example of removing alignment-specific validation (if it exists):
       # if start_time != get_interval_floor(start_time, interval):
       #     raise ValueError("Start time is not aligned to interval.")
   // ... existing code ...
   ```
   ````

4. **`core/vision_data_client.py`**:

   - **Action**: Adjust `fetch` and `_download_and_cache` to implement manual time boundary adjustments _to align with REST API behavior_. **In `_download_and_cache`, ensure the loop iterates through dates and applies manual alignment to mimic REST API boundaries. Use `ApiBoundaryValidator` to determine the correct alignment logic.** Review `_get_cache_path` and ensure it uses the aligned date. In `_validate_cache`, adapt checks to validate against REST API-like time alignment.
   - **Code Change**:

   ````diff
   ```language:core/vision_data_client.py
   // ... existing code ...
   async def _download_and_cache(
       self,
       start_time: datetime,
       end_time: datetime,
       columns: Optional[Sequence[str]] = None,
   ) -> TimestampedDataFrame:
       """Downloads and caches data for the given date range."""
       all_dfs = []
       current_date = start_time.date() # Start from the start_time's date
       end_date = end_time.date() # End at the end_time's date

       while current_date <= end_date: # Loop through dates and apply manual alignment *to match REST API*
           # Apply manual time alignment here for current_date to mimic REST API boundaries
           aligned_date = self._align_date_to_rest_api_boundary(datetime(current_date.year, current_date.month, current_date.day)) # Example - implement _align_date_to_rest_api_boundary using ApiBoundaryValidator
           cache_path = self._get_cache_path(aligned_date) # Use aligned_date for cache path
           cached_df = await self._check_cache(aligned_date, columns=columns) # Use aligned_date
           if cached_df is not None:
               all_dfs.append(cached_df)
           else:
               df = await self._download_daily_data(aligned_date) # Use aligned_date
               if not df.empty:
                   await self._save_to_cache(df, aligned_date) # Use aligned_date
                   all_dfs.append(df)
           current_date += timedelta(days=1)

       if not all_dfs:
           return self._create_empty_dataframe()

       combined_df = pd.concat(all_dfs).sort_index()
       return TimestampedDataFrame(combined_df)

   def _get_cache_path(self, date: datetime) -> Path:
       """Get the cache path for a specific date. - Ensure *aligned* date is used"""
       date_str = date.strftime("%Y-%m-%d") # Use *aligned* date for path
       filename = f"{self.symbol}-{self.interval}-{date_str}{FileExtensions.CACHE.value}"
       return self.cache_dir / filename

   def _validate_cache(self, start_time: datetime, end_time: datetime) -> bool:
       """Validate cache for the time range. - Adapt checks to validate against REST API-like alignment"""
       # Remove any checks that were validating based on *old* aligned time boundaries
       # Add checks to validate against *REST API-like* time boundaries using ApiBoundaryValidator
       # Example:
       # is_api_aligned = await self.api_boundary_validator.does_data_range_match_api_response(cached_df, expected_start_time, expected_end_time, interval)
       # if not is_api_aligned:
       #     return False
       return True # Ensure basic validation logic remains if needed (e.g., file existence, checksum)

   # Add a new method to handle alignment based on REST API behavior
   # async def _align_date_to_rest_api_boundary(self, date: datetime) -> datetime:
   #     """Align date to mimic REST API boundary behavior using ApiBoundaryValidator."""
   #     # Implement logic here using ApiBoundaryValidator to get REST API boundaries for the date and interval
   #     # and adjust the date accordingly. This is a placeholder - actual implementation will depend on
   #     # how REST API alignment needs to be applied to Vision API and cache.
   #     return date # Placeholder - replace with actual alignment logic

   // ... existing code ...
   ```
   ````

5. **`core/cache_manager.py`**:

   - **Action**: Modify `get_cache_key`, `save_to_cache`, and `load_from_cache` to ensure they work correctly with manual alignment _for cache to mimic REST API behavior_. **In `get_cache_key` and `get_cache_path`, ensure _aligned_ date is used for key/path generation.** In `save_to_cache` and `load_from_cache`, implement logic to handle data that is manually aligned to REST API boundaries.
   - **Code Change**:

   ````diff
   ```language:core/cache_manager.py
   // ... existing code ...
   def get_cache_path(self, symbol: str, interval: str, date: datetime) -> Path:
       """Get cache file path following the simplified structure. - Use *aligned* date"""
       return CacheKeyManager.get_cache_path(self.data_dir, symbol, interval, date) # Date should be *aligned* datetime object

   def get_cache_key(self, symbol: str, interval: str, date: datetime) -> str:
       """Generate cache key. - Use *aligned* date"""
       return CacheKeyManager.get_cache_key(symbol, interval, date) # Date should be *aligned* datetime object

   async def save_to_cache( # In save_to_cache, ensure data being saved is *aligned* to REST API boundaries
       self, df: pd.DataFrame, symbol: str, interval: str, date: datetime
   ) -> Tuple[str, int]:
       """Save DataFrame to cache."""
       # Ensure date has proper timezone using TimeRangeManager - Keep timezone enforcement, but date should be *aligned* already
       date = TimeRangeManager.enforce_utc_timezone(date) # Date should be *aligned* before this

       // ... existing code ...

   async def load_from_cache( # In load_from_cache, ensure no assumptions about *old* time alignment, but handle *REST API-like* aligned data
       self,
       symbol: str,
       interval: str,
       date: datetime,
       columns: Optional[Sequence[str]] = None,
   ) -> Optional[pd.DataFrame]:
       """Load data from cache if available."""
       // ... existing code ...
       # Ensure index has correct timezone using TimeRangeManager - Keep timezone enforcement, but no *old* alignment assumptions
       if isinstance(df.index, pd.DatetimeIndex):
           new_index = pd.DatetimeIndex(
               [
                   TimeRangeManager.enforce_utc_timezone(dt)
                   for dt in df.index.to_pydatetime()
               ],
               name=df.index.name,
           )
           df.index = new_index
       // ... existing code ...
   ```
   ````

6. **`utils/validation.py` and `utils/cache_validator.py`**:

   - **Action**: Review time-related validation functions in both files. **In `validation.py`, remove `validate_time_boundaries` as it likely enforces boundary alignment that is no longer needed for REST API calls.** In `cache_validator.py`, review `validate_cache_integrity` and `validate_cache_data` and adapt or add validation logic to ensure cached data and integrity are consistent with REST API boundary behavior. Use `ApiBoundaryValidator` for these validations.
   - **Code Change**:

   ````diff
   ```language:utils/validation.py
   // ... existing code ...
   class DataValidation:
       // ... existing code ...

       # @staticmethod - REMOVE validate_time_boundaries entirely *as it's not needed for REST API calls*
       # def validate_time_boundaries(
       #     df: pd.DataFrame, start_time: datetime, end_time: datetime
       # ) -> None:
       #     """Validate that DataFrame covers the requested time range."""
       #     ... # Old alignment specific validation logic - REMOVE

       // ... existing code ...
   ```
   ````

   ````diff
   ```language:utils/cache_validator.py
   // ... existing code ...
   class CacheValidator:
       // ... existing code ...
       @classmethod
       def validate_cache_data(
           cls, df: pd.DataFrame, allow_empty: bool = False, api_boundary_validator: ApiBoundaryValidator = None # Inject validator if needed
       ) -> Optional[CacheValidationError]:
           """Validate cached data DataFrame. - Remove *old* alignment specific checks, add checks for REST API-like alignment"""
           if df.empty and not allow_empty:
               return CacheValidationError(
                   error_type=ERROR_TYPES["VALIDATION"],
                   message="DataFrame is empty",
                   is_recoverable=True,
               )
           try:
               DataFrameValidator.validate_dataframe(df)
           except ValueError as e:
               return CacheValidationError(
                   error_type=ERROR_TYPES["VALIDATION"],
                   message=f"DataFrame validation failed: {e}",
                   is_recoverable=False, # Data integrity issue, not recoverable
               )
           # Remove any *old* alignment specific data validation here
           # Example of removing old alignment validation (if it exists):
           # if not TimeRangeManager.is_data_aligned_to_interval(df, interval):
           #     return CacheValidationError(...)

           # Add validation to ensure data is aligned to REST API boundaries using ApiBoundaryValidator
           # if api_boundary_validator:
           #     is_api_aligned = api_boundary_validator.does_data_range_match_api_response(df, expected_start_time, expected_end_time, interval)
           #     if not is_api_aligned:
           #         return CacheValidationError(...)

           return None

       @classmethod
       def validate_cache_integrity(
           cls,
           cache_path: Path,
           max_age: timedelta = None,
           min_size: int = None,
       ) -> Optional[CacheValidationError]:
           """Validate cache file integrity. - Remove *old* time alignment related checks, adapt for REST API-like alignment if needed"""
           error = None
           if not cache_path.exists():
               error =  CacheValidationError(
                   error_type=ERROR_TYPES["FILE_SYSTEM"],
                   message=f"Cache file does not exist: {cache_path}",
                   is_recoverable=False, # Critical file missing
               )
           elif min_size and cache_path.stat().st_size < min_size:
               error = CacheValidationError(
                   error_type=ERROR_TYPES["DATA_INTEGRITY"],
                   message=f"Cache file too small: {cache_path}",
                   is_recoverable=True, # Incomplete download, recoverable
               )
           if error:
               return error

           # Remove any *old* time-alignment related integrity checks here if present
           # Example of removing old time alignment check (if it exists):
           # if not cls._is_cache_time_aligned(cache_path):
           #     return CacheValidationError(...)

           if max_age and cls._is_cache_expired(cache_path, max_age):
               return CacheValidationError(
                   error_type=ERROR_TYPES["CACHE_INVALID"],
                   message=f"Cache expired: {cache_path}",
                   is_recoverable=True, # Stale data, recoverable
               )
           return None

   // ... existing code ...
   ```
   ````

7. **`utils/config.py`**:

   - **Action**: Review time-related configurations. **Remove any configurations that are directly related to _old_ time alignment offsets or adjustments.** Configurations like `CONSOLIDATION_DELAY`, `MAX_TIME_RANGE`, `INCOMPLETE_BAR_THRESHOLD` are likely still relevant for other purposes (data availability, request limits, etc.) and should be retained unless they are explicitly tied to the removed _old_ alignment logic.
   - **Code Change**:

   ````diff
   ```language:utils/config.py
   // ... existing code ...
   # Time constraints - Review these, but likely keep them if they are for API limits or data availability, not *old* alignment
   CONSOLIDATION_DELAY: Final = timedelta(hours=48)
   MAX_TIME_RANGE: Final = timedelta(days=30)  # Maximum time range for single request
   MAX_HISTORICAL_DAYS: Final = 1000  # Maximum days back for historical data
   INCOMPLETE_BAR_THRESHOLD: Final = timedelta(
       minutes=5
   )  # Time after which bars are considered complete

   # Remove any *old* alignment specific configurations if they exist
   # Example of removing old alignment specific config (if it exists):
   # TIME_ALIGNMENT_OFFSET: Final = timedelta(milliseconds=100) # No longer needed

   // ... existing code ...
   ```
   ````

## Phase 5: Testing and Verification (Full System) (and subsequent phases from original roadmap)

1. **Implement Unit and Integration Tests**:

   - **Action**: Write comprehensive unit and integration tests focusing on time boundary handling **aligned with Binance REST API behavior**. Test various scenarios, including:
     - Exact boundary requests as defined by REST API
     - Millisecond precision in start and end times **(Crucial test case to verify REST API alignment)**
     - Cross-day, cross-month, and cross-year boundary requests **(Verify REST API alignment across boundaries)**
     - Different intervals (1s, 1m, 1h, 1d, etc.) **(Verify REST API alignment across intervals)**
     - Cache save and load operations across time boundaries **(Ensure cache alignment matches REST API)**
     - REST and Vision API data consistency in time handling **(Verify Vision API manual alignment matches REST API)**
     - **Test for correct data retrieval at interval boundaries as described in `docs/api/binance_rest_api_boundary_behaviour.md`. Crucially, test that Vision API and cache now behave _exactly_ like REST API in terms of time boundaries.**
   - **Tools**: Utilize `pytest` and potentially create new test modules specifically for time boundary testing. **Create tests that assert the _presence_ of manual time alignment in Vision API and cache to match REST API behavior, and the _absence_ of manual time alignment for REST API calls themselves.**

2. **Run Tests and Debug**:

   - **Action**: Execute all tests and debug any failures. Pay close attention to tests related to time boundaries and caching. **Use debuggers and logging to trace timestamps throughout the data retrieval and caching process to ensure Vision API and cache alignment is happening correctly and REST API calls are not being manually aligned.**
   - **Command**: `scripts/run_tests_parallel.sh tests/your_time_boundary_tests`

3. **Performance and Regression Testing**:
   - **Action**: Conduct performance tests to ensure the revamped codebase maintains or improves performance. Perform regression testing to confirm no existing functionality is broken. **Pay attention to any performance changes due to the changes in time alignment logic. Regression test all existing functionalities to ensure no unintended side effects.**

## Phase 6: Documentation and Cleanup (and subsequent phases from original roadmap)

1. **Update Documentation**:

   - **Action**: Update any relevant documentation (including `docs/api/binance_rest_api_boundary_behaviour.md` and code comments) to reflect the changes in time alignment strategy. **Document the shift to REST API-like alignment for Vision API and cache, and the removal of manual alignment for REST API calls. Update code comments to reflect these changes.**

2. **Code Cleanup**:
   - **Action**: Remove any commented-out code, deprecated functions, and ensure the codebase is clean and well-organized after the revamp. **Perform a final code review to remove any dead code, simplify logic, and improve readability after the refactoring, especially focusing on time alignment related code.**

This revised roadmap clarifies that we are aiming for **REST API-like time alignment for Vision API and cache**, and **removing manual alignment for REST API calls**. Let's continue with **Phase 1, Step 1: Ensuring `utils/api_boundary_validator.py` is robust and accurately reflects Binance REST API behavior.** Are you ready to proceed with reviewing and potentially enhancing the `ApiBoundaryValidator` tests to ensure comprehensive coverage of Binance REST API boundary behavior?
