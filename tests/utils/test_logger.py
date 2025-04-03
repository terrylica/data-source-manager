import logging
from utils.logger_setup import logger


def test_logger_with_caplog(caplog):
    """Test that our custom logger works correctly with pytest's caplog fixture."""
    # Set the capture level to DEBUG to see all logs
    caplog.set_level(logging.DEBUG)

    # Use the logger directly from logger_setup
    # No need to create a new logger instance

    # Generate some log messages
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

    # Print out caplog records for debugging
    print("\nCAPLOG RECORDS:")
    for i, record in enumerate(caplog.records):
        print(f"Record {i}: {record}")
        print(f"  - name: {record.name}")
        print(f"  - levelname: {record.levelname}")
        print(f"  - message: {record.message}")

    # Verify that messages are captured
    assert len(caplog.records) > 0, "No log records were captured!"

    # Check specific messages (now with direct string matching)
    assert any(record.message == "This is an info message" for record in caplog.records)
    assert any(
        record.message == "This is a warning message" for record in caplog.records
    )
    assert any(
        record.message == "This is an error message" for record in caplog.records
    )


def test_multiple_log_levels_with_caplog(caplog):
    """Test capturing different log levels."""
    # Clear any previous records
    caplog.clear()

    # Set level to WARNING
    caplog.set_level(logging.WARNING)

    # Use the logger directly
    logger.info("Info should not be captured")
    logger.warning("Warning should be captured")

    # Print out caplog records for debugging
    print("\nCAPLOG RECORDS (WARNING level):")
    for i, record in enumerate(caplog.records):
        print(f"Record {i}: {record.message} (level: {record.levelname})")

    # Only WARNING or higher should be captured
    assert not any(record.levelname == "INFO" for record in caplog.records)
    assert any(
        record.message == "Warning should be captured" for record in caplog.records
    )
