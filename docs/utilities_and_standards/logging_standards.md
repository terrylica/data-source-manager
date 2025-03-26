# Logging Standards: Pytest Caplog Integration

## Overview

This document defines the project's logging standards and implementation, with a focus on compatibility with pytest's `caplog` fixture. Our logging implementation uses Python's standard `logging.StreamHandler` enhanced with `colorlog` for colored output, ensuring proper integration with testing tools while maintaining readability.

The logging standards described here **must be followed for all new code** to ensure consistent logging behavior and testability across the project.

## Changes Made

The following changes were implemented:

1. **Replaced `RichHandler` with `logging.StreamHandler`**:

   - Switched from the Rich library's `RichHandler` to Python's standard `logging.StreamHandler`
   - This is more compatible with standard Python logging patterns and pytest's `caplog`

2. **Added `colorlog` for Colorized Output**:

   - Installed and integrated the `colorlog` package
   - Configured `ColoredFormatter` to maintain colorized console output

3. **Modified Log Propagation**:

   - Set `logger.propagate = True` to ensure logs propagate to the root logger
   - This is essential for pytest's `caplog` fixture to capture the logs

4. **Created Logger Tests**:
   - Added tests in `tests/utils/test_logger.py` to verify correct integration with pytest's `caplog`
   - Verified existing tests continue to work with the new logger implementation

## Implementation Details

### Before

```python
# Previous implementation with RichHandler
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            markup=True,
            show_path=True,
            omit_repeated_times=True,
            log_time_format="[%X]"
        )
    ],
    force=True
)
```

### After

```python
# New implementation with StreamHandler and ColoredFormatter
def get_logger(name: str, level: str = None, show_path: bool = None, rich_tracebacks: bool = True) -> logging.Logger:
    logger = logging.getLogger(name)
    log_level = level.upper() if level else console_log_level
    logger.setLevel(log_level)

    # Only add a handler if the logger doesn't already have one
    if not logger.handlers:
        # Create a handler that writes log messages to stderr
        handler = logging.StreamHandler()

        # Create colored formatter for console output
        console_format = "%(levelname)-8s"
        if show_path is None or show_path:
            console_format += " %(name)s:"
        console_format += " %(message)s"

        # Create a ColoredFormatter
        formatter = ColoredFormatter(
            console_format,
            datefmt="[%X]",
            log_colors={
                'DEBUG':    'cyan',
                'INFO':     'green',
                'WARNING':  'yellow',
                'ERROR':    'red',
                'CRITICAL': 'red,bg_white',
            },
            style='%'
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # IMPORTANT: Leave propagate as True for pytest caplog to work
    logger.propagate = True

    return logger
```

## Benefits

1. **Improved Testing**: Log messages can now be properly captured and tested using pytest's `caplog` fixture
2. **Maintained Readability**: Color-coded logs are still available, maintaining the visual benefits
3. **Simplified Debugging**: More reliable log capturing makes it easier to debug issues with tests
4. **Standard Approach**: Uses Python's standard logging mechanisms, making the code more maintainable

## Dependencies Added

- **colorlog**: A package that adds color to Python logging output.

## Compatibility

This change has been verified to work with:

- Existing tests that use the `caplog` fixture
- New dedicated logger tests
- Normal console output scenarios

## Usage Guidelines

### Standard Usage

For most use cases, simply import the logger and use it as follows:

```python
from utils.logger_setup import get_logger

# Create a logger with the module name
logger = get_logger(__name__)

# Log messages at appropriate levels
logger.debug("Detailed information, typically of interest only when diagnosing problems")
logger.info("Confirmation that things are working as expected")
logger.warning("An indication that something unexpected happened, or may happen in the near future")
logger.error("Due to a more serious problem, the software has not been able to perform a function")
logger.critical("A serious error, indicating that the program itself may be unable to continue running")
```

### Custom Log Levels

To specify a custom log level:

```python
logger = get_logger(__name__, level="DEBUG")
```

### Control Path Display

To hide the module path in logs:

```python
logger = get_logger(__name__, show_path=False)
```

### Testing with Caplog

When writing tests that verify logging behavior, use pytest's `caplog` fixture:

```python
def test_function_with_logging(caplog):
    # Set the log level for the test
    caplog.set_level(logging.INFO)

    # Call the function that logs
    some_function_that_logs()

    # Verify log messages
    assert "Expected log message" in caplog.text

    # Or check specific records
    for record in caplog.records:
        if record.levelname == "ERROR":
            assert "specific error message" in record.message
```

## Conventions to Follow

1. **Always use the `get_logger` function** from `utils.logger_setup` to create loggers, never instantiate Python's logging classes directly.

2. **Use appropriate log levels**:

   - `DEBUG`: Detailed information for diagnostics
   - `INFO`: Normal program operation
   - `WARNING`: Unexpected situations that don't prevent operation
   - `ERROR`: Errors that prevent specific operations
   - `CRITICAL`: Errors that may prevent the entire program from functioning

3. **Include context** in log messages to make them actionable and informative.

4. **Keep logger propagation enabled** (the default in our implementation) to ensure proper interaction with pytest's `caplog`.

5. **Write tests for logging behavior** when logging is an important part of a component's functionality.

## Future Considerations

If additional customization is needed for the log format or colors, the `ColoredFormatter` configuration in `logger_setup.py` can be modified.
