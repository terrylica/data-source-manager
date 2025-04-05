# Testing Utilities

This directory contains utilities for testing the codebase, with a focus on enhancing the testing experience and addressing common testing challenges.

## Unified Logging (`unified_logging.py`)

The centerpiece of our testing utilities is the unified logging abstraction, which provides a robust solution for capturing logs during test execution, particularly in parallel environments using pytest-xdist.

### Key Features

- **Parallel-Safe Log Capture**: Works seamlessly with pytest-xdist for parallel test execution
- **Consistent API**: Provides a drop-in replacement for pytest's native caplog fixture
- **Comprehensive Debug Support**: Ensures DEBUG level logs are properly captured and filtered
- **Resource Cleanup**: Automatically cleans up logging handlers to prevent resource leaks
- **Contextual Level Management**: Supports temporary log level changes via context managers
- **Backward Compatibility**: Maintains compatibility with existing tests via the `caplog_xdist_compatible` fixture

### Usage Examples

#### Basic Usage

```python
def test_with_unified_logging(caplog_unified):
    # Set the capture level
    caplog_unified.set_level(logging.DEBUG)

    # Generate logs
    logger.debug("Debug message")
    logger.info("Info message")

    # Assert logs were captured
    assert_log_contains(caplog_unified, "Debug message", logging.DEBUG)
    assert_log_contains(caplog_unified, "Info message", logging.INFO)
```

#### Contextual Log Level Changes

```python
def test_with_context_manager(caplog_unified):
    # Set base level to ERROR
    caplog_unified.set_level(logging.ERROR)

    # Temporarily lower threshold to INFO within context
    with caplog_unified.at_level(logging.INFO):
        logger.info("This info message will be captured")

    # Back to ERROR threshold
    logger.info("This info message will be filtered out")
```

#### Asynchronous Test Support

```python
@pytest.mark.asyncio
async def test_async_with_logs(caplog_unified):
    caplog_unified.set_level(logging.DEBUG)

    logger.info("Starting async operation")
    await asyncio.sleep(0.1)
    logger.debug("Operation in progress")

    # Filter out asyncio infrastructure logs
    our_module_logs = [
        r for r in caplog_unified.records
        if r.name == "your.module.name"
    ]
```

### Available Fixtures

- **`caplog_unified`**: The recommended fixture for new tests
- **`caplog_xdist_compatible`**: For backward compatibility with existing tests
- **`caplog`**: Enhanced version of pytest's native caplog that works with pytest-xdist

### Helper Functions

- **`assert_log_contains`**: Asserts that a specific log message was captured
- **`configure_root_logger_for_testing`**: Ensures proper logging configuration for tests

## Other Testing Utilities

- **`debug_helpers.py`**: Utility functions for debugging test issues
- **`dataframe_validation.py`**: Validation helpers for DataFrame structures
- **`cache_test_utils.py`**: Utilities for testing caching behavior

## Best Practices

1. Use `caplog_unified` for all new tests that need to capture logs
2. Filter logs by module name when testing in noisy environments
3. Use `at_level` context manager for temporary log level changes
4. Always ensure proper cleanup by using the fixture (don't instantiate directly)
5. Mark tests that shouldn't run in parallel with `@pytest.mark.serial`
