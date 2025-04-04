# Integrated Testing Solution for Async Code and Parallel Execution

This directory contains an example implementation that integrates best practices from both:

- pytest-asyncio for event loop management
- pytest-xdist for parallel test execution
- Logging capture in a parallel environment

## Key Components

### 1. Enhanced conftest.py

The `conftest.py` file contains critical configuration for reliable parallel test execution:

- **Event Loop Configuration**: Properly configures asyncio loop scope via pytest_configure
- **Custom Caplog Fixture**: A simplified, xdist-compatible logging capture fixture
- **Custom Markers**: Registers a "serial" marker for tests that should run sequentially

### 2. Test Best Practices

The sample test file demonstrates several best practices:

- **Isolated Async Tests**: Each async test is marked individually with @pytest.mark.asyncio
- **Reliable Log Capture**: Uses a custom xdist-compatible caplog fixture
- **Parallel-Safe Assertions**: Test assertions work correctly in parallel mode
- **Serial Test Option**: Tests that need to run serially are marked appropriately

## Usage Guide

### Running Tests

Run tests normally:

```bash
pytest test_combined_practices.py -v
```

Run tests in parallel mode:

```bash
pytest test_combined_practices.py -v -n 2
```

Run only serial tests:

```bash
pytest test_combined_practices.py -v -m serial
```

### Implementing These Patterns

To implement these patterns in your own codebase:

1. **Copy the conftest.py**: Include the enhanced configuration in your project
2. **Use the Custom Caplog**: Replace `caplog` with `caplog_xdist_compatible` in your tests
3. **Mark Async Tests**: Use `@pytest.mark.asyncio` on async test functions
4. **Mark Serial Tests**: Use `@pytest.mark.serial` for tests that should run sequentially
5. **Update Test Runner**: Ensure your test runner sets appropriate asyncio configuration

## How It Works

### Event Loop Management

- Each test gets a fresh event loop with function scope
- Using `asyncio_default_fixture_loop_scope="function"` configuration prevents KeyError issues when running in parallel
- With pytest-xdist 3.6.0+ and execnet 2.1.0+, tests run in the main thread of worker processes

### Logging Capture

- The custom caplog fixture avoids the KeyError issues with the standard caplog fixture
- It provides a compatible API while ensuring proper logging capture in parallel execution
- Handler cleanup ensures test isolation and prevents memory leaks

### Test Marking

- Serial tests are properly marked, allowing them to be run separately if needed
- This approach balances test isolation with performance requirements

## Version Requirements

- Python 3.8+
- pytest 7.0.0+
- pytest-asyncio 0.26.0+
- pytest-xdist 3.6.0+
- execnet 2.1.0+
