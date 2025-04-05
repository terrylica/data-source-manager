import logging
from utils.logger_setup import logger

"""
Legacy test file for the logger_setup module.

IMPORTANT: This file is kept for backward compatibility with existing tests.
For new tests, please use the unified logging approach demonstrated in 
tests/utils/test_unified_logging.py which provides better support for 
parallel test execution with pytest-xdist.

This file uses caplog_xdist_compatible which is implemented using our
UnifiedLogCapture abstraction (see tests/utils/unified_logging.py).
"""

# Note: This file maintains the original test functions for backward compatibility.
# The tests use caplog_xdist_compatible which is now implemented using our
# UnifiedLogCapture abstraction (see tests/utils/unified_logging.py).
# New tests should use the unified approach demonstrated in test_unified_logging.py.


def test_logger_with_caplog(caplog_xdist_compatible):
    """Test that our custom logger works correctly with pytest's caplog fixture."""
    # Set the capture level to DEBUG to see all logs
    caplog_xdist_compatible.set_level(logging.DEBUG)

    # Use the logger directly from logger_setup
    # No need to create a new logger instance

    # Generate some log messages
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Print out caplog records for debugging
    print("\nCAPLOG RECORDS:")
    for i, record in enumerate(caplog_xdist_compatible.records):
        print(f"Record {i}: {record}")
        print(f"  - name: {record.name}")
        print(f"  - levelname: {record.levelname}")
        print(f"  - message: {record.message}")

    # Verify that messages are captured
    assert len(caplog_xdist_compatible.records) > 0, "No log records were captured!"

    # Check specific messages (now with direct string matching)
    assert any(
        record.message == "This is an info message"
        for record in caplog_xdist_compatible.records
    )
    assert any(
        record.message == "This is a warning message"
        for record in caplog_xdist_compatible.records
    )
    assert any(
        record.message == "This is an error message"
        for record in caplog_xdist_compatible.records
    )


def test_multiple_log_levels_with_caplog(caplog_xdist_compatible):
    """Test capturing different log levels."""
    # Clear any previous records
    caplog_xdist_compatible.clear()

    # Set level to WARNING
    caplog_xdist_compatible.set_level(logging.WARNING)

    # Use the logger directly
    logger.info("Info should not be captured")
    logger.warning("Warning should be captured")

    # Print out caplog records for debugging
    print("\nCAPLOG RECORDS (WARNING level):")
    for i, record in enumerate(caplog_xdist_compatible.records):
        print(f"Record {i}: {record.message} (level: {record.levelname})")

    # Only WARNING or higher should be captured
    assert not any(
        record.levelname == "INFO" for record in caplog_xdist_compatible.records
    )
    assert any(
        record.message == "Warning should be captured"
        for record in caplog_xdist_compatible.records
    )
