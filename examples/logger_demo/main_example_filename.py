"""
Demonstration of logger filename display feature.

This example shows how to enable filename display in log messages,
which helps identify the source file of each log entry.
"""

# Standard module-level logger import
from utils.logger_setup import logger
from examples.logger_demo.test_modules import do_task_a, do_task_b

# Set log level to INFO for clear output
logger.setLevel("INFO")


def main():
    """Demonstrate filename display in log messages."""
    # Without filename display (default)
    logger.info("Log message without filename (default)")

    # Enable filename display
    logger.show_filename(True)
    logger.info("Log message WITH filename display enabled")

    # Demonstrate the feature with imported modules
    # The filename of each module will be displayed in the logs
    result_a = do_task_a()
    result_b = do_task_b()

    # Fluent interface works with this setting too
    logger.info("Chained method calls work too").warning("Still shows filename")

    # Disable filename display
    logger.show_filename(False)
    logger.info("Filename display disabled again")

    # Turn it back on with rich formatting if available
    try:
        logger.use_rich(True).show_filename(True)
        logger.info("Rich logging with filename display")
    except Exception as e:
        logger.error(f"Could not enable rich logging: {e}")
    finally:
        # Reset to standard logging
        logger.use_rich(False)


if __name__ == "__main__":
    main()

    # Display implementation usage pattern
    print("\nFilename Display Feature Usage:")
    print("1. Basic usage:")
    print("   logger.show_filename(True)  # Enable filename display")
    print("   logger.show_filename(False)  # Disable filename display")
    print("\n2. Method chaining:")
    print("   logger.setLevel('INFO').show_filename(True)")
    print("\n3. With rich logging:")
    print("   logger.use_rich(True).show_filename(True)")
    print("\n4. Environment variable:")
    print(
        "   SHOW_LOG_FILENAME=true python examples/logger_demo/main_example_filename.py"
    )
