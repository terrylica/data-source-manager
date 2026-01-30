# Unified Logging Abstraction

This document outlines the unified logging abstraction implementation for the testing infrastructure. The implementation follows the principles of Occam's Razor and the Liskov Substitution Principle to create a robust, unified approach to log capturing in tests.

## Key Principles Applied

### Occam's Razor

> "Entities should not be multiplied beyond necessity."

We've applied this principle by:

1. **Creating a single unified logging implementation** rather than multiple specialized solutions
2. **Consolidating duplicate code** across multiple test files into a single abstraction
3. **Providing a minimal but complete API** that handles all use cases without unnecessary complexity
4. **Replacing multiple custom fixtures** with a single, comprehensive approach

### Liskov Substitution Principle

> "Objects of a superclass should be replaceable with objects of its subclasses without breaking the application."

We've applied this principle by:

1. **Ensuring backwards compatibility** with existing tests
2. **Maintaining the same interface** as pytest's native `caplog` fixture
3. **Supporting both synchronous and asynchronous tests** with the same abstraction
4. **Working correctly in both sequential and parallel execution** environments

## Implementation Details

The unified logging abstraction is implemented in `tests/utils/unified_logging.py` and consists of:

### Core Components

1. **`UnifiedLogCapture` Class**
   - Captures logs during test execution
   - Works with both synchronous and asynchronous tests
   - Compatible with pytest-xdist parallel execution
   - Handles log level filtering correctly
   - Provides context managers for temporary log level changes
   - Ensures proper cleanup of resources

2. **Global Fixtures**
   - `caplog_unified`: The recommended fixture for new tests
   - `caplog_xdist_compatible`: For backward compatibility with existing tests
   - `caplog`: Enhanced version of pytest's native fixture

3. **Helper Functions**
   - `assert_log_contains`: For verifying log messages
   - `configure_root_logger_for_testing`: For proper logger setup

### Integration with pytest

The implementation is integrated with pytest through:

1. **Root `conftest.py`** imports and re-exports the fixtures
2. **`pytest_configure` function** configures the asyncio event loop scope
3. **Default log level configuration** ensures DEBUG logs are captured

## Migration from Legacy Approaches

The following legacy approaches have been replaced:

1. **Custom `DummyCaplog` implementations** in individual test files
2. **Manual logger configuration** in test setup functions
3. **Inconsistent log capturing mechanisms** across different test directories
4. **Special handling for pytest-xdist compatibility** in multiple places

## Usage Examples

### Basic Usage

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

### Asynchronous Tests

```python
@pytest.mark.asyncio
async def test_async_logging(caplog_unified):
    caplog_unified.set_level(logging.DEBUG)

    logger.info("Starting async operation")
    await asyncio.sleep(0.1)
    logger.debug("Operation in progress")

    assert_log_contains(caplog_unified, "Starting async operation")
    assert_log_contains(caplog_unified, "Operation in progress")
```

### Temporary Log Level Changes

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

## Benefits and Future Directions

### Benefits

1. **Simplified Testing Code**: Reduced boilerplate and duplication
2. **Consistent Behavior**: Same approach works everywhere
3. **Improved Reliability**: No more flaky tests due to logging issues
4. **Better Debug Support**: Comprehensive log capture for debugging

### Future Directions

1. **Log Filtering by Module**: Add specialized filtering options
2. **Structured Log Support**: Enhance for structured logging formats
3. **Performance Optimization**: Optimize for very high throughput scenarios
4. **Configuration Options**: Add more flexibility for specialized use cases
