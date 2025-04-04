# Resolving KeyError Issues with pytest-asyncio and pytest-xdist

The KeyError you're encountering with pytest-asyncio when used alongside pytest-xdist (parallel execution with -nX) typically results from race conditions or issues accessing the asynchronous event loop across test processes.

## Root Cause

The fundamental issue occurs because pytest-xdist's worker processes may execute tests in non-main threads. This creates problems with asyncio-based code that expects to run in the main thread, particularly when interacting with signals, which can only be handled in the main thread.

## Latest Solutions (2024)

### Use pytest-xdist 3.6.0+ with Execnet Main Thread Only Mode

As of pytest-xdist 3.6.0+ (released April 2024), a significant improvement was made to address this issue permanently. The plugin now uses the new `main_thread_only` execmodel from execnet 2.1.0+, ensuring that worker code always runs in the main thread:

```bash
# Make sure you're using the latest versions
pip install pytest-xdist>=3.6.0 execnet>=2.1.0
```

This change fixes issues like:

- RuntimeError when using signal handlers (set_wakeup_fd only works in main thread)
- KeyError in worker process communication
- Issues with pytest-asyncio event loop management

### Minimum Requirements

For the latest fixed version:

- Python 3.8+
- pytest 7.0.0+
- execnet 2.1.0+
- pytest-xdist 3.6.0+

## Best Practices for Event Loop Management

1. Use Explicit Event Loop Fixtures

Ensure each async test explicitly gets its own isolated event loop:

```python
import pytest
import asyncio

@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

This avoids cross-test interference and isolates state per test, mitigating the cause of the KeyError.

1. Avoid Global State

Avoid reliance on global objects or cached references between tests. Pytest-xdist (-nX) creates multiple subprocesses, and sharing global mutable state across processes can lead to KeyError.

Ensure your test setup and teardown logic never references shared globals:

Bad:

```python
GLOBAL_LOOP = asyncio.get_event_loop()

@pytest.mark.asyncio
async def test_example():
    await GLOBAL_LOOP.run_in_executor(None, some_func)
```

Good:

```python
@pytest.mark.asyncio
async def test_example(event_loop):
    await event_loop.run_in_executor(None, some_func)
```

1. Use Proper Fixture Scoping

Keep the event loop fixture at the function level to isolate tests completely:

```python
@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

Do not set broader scopes (session or module) when running with pytest-xdist.

1. Configure pytest.ini Properly

Make sure your project explicitly defines asyncio mode in pytest.ini:

```ini
[pytest]
asyncio_mode = auto
```

Setting the asyncio mode explicitly helps pytest-asyncio manage event loops properly in distributed execution.

1. Separate Async Tests from Sync Tests

If possible, isolate async tests into their own test modules or directories. This practice improves reliability and clearly isolates parallel execution concerns:

```text
tests/
├── async_tests/
│   └── test_async_example.py
└── sync_tests/
    └── test_sync_example.py
```

Run async tests separately, if issues persist:

```bash
pytest tests/async_tests -n auto
pytest tests/sync_tests -n auto
```

1. Ensure Compatibility Between Plugins

Confirm you have the latest compatible versions:

```bash
pip install --upgrade pytest pytest-asyncio pytest-xdist
```

Occasionally, incompatibilities arise due to outdated plugin interactions.

## Alternative Approaches

### Using Custom concurrency within Tests

For maximum control over concurrency without relying on pytest-xdist, you can use pytest-subtests to run concurrent operations within a single test:

```python
import pytest
import asyncio
import time

pytestmark = pytest.mark.asyncio

async def test_concurrent_operations(subtests):
    async def async_operation(name, duration):
        with subtests.test(msg=f"Operation {name}"):
            start = time.time()
            await asyncio.sleep(duration)
            assert time.time() - start >= duration

    # Run operations concurrently
    await asyncio.gather(
        async_operation("A", 1),
        async_operation("B", 2),
        async_operation("C", 1.5)
    )
```

### Using pytest-asyncio-cooperative

For more sophisticated async test concurrency, consider pytest-asyncio-cooperative:

```bash
pip install pytest-asyncio-cooperative
```

This plugin allows running multiple async tests concurrently while maintaining proper isolation:

```python
import pytest

# Mark tests that can run concurrently
pytestmark = [pytest.mark.asyncio, pytest.mark.asyncio_cooperative]

async def test_operation_1():
    # This can run concurrently with other tests
    await asyncio.sleep(1)
    assert True

async def test_operation_2():
    # This can run concurrently with other tests
    await asyncio.sleep(1)
    assert True
```

Note: When using pytest-asyncio-cooperative, be careful with shared resources and mocking. As of version 0.17.1+, you can use "fixture locks" to prevent race conditions.

## Recommended Approach

A concise, stable setup to avoid KeyError with pytest-asyncio and pytest-xdist is:

```python
# conftest.py

import pytest
import asyncio

@pytest.fixture(scope="function")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

With:

```ini
[pytest]
asyncio_mode = auto
```

Then run your tests with:

```bash
pytest -n auto
```

By following these practices and using the latest versions of pytest-xdist (3.6.0+) and execnet (2.1.0+), you can avoid the KeyError issues that previously affected async tests running in parallel.
