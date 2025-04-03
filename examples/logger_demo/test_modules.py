"""
Library module demonstrating logging hierarchy propagation.

This module illustrates the component module logging pattern, which requires
no explicit configuration when imported by a properly configured application.
"""

from utils.logger_setup import logger


def do_task_a():
    """
    Execute task A with comprehensive logging.

    Demonstrates component module logging with hierarchical level propagation
    from the application's root logger configuration.

    Returns:
        str: Task execution result identifier
    """
    logger.debug("Debug message from test_modules.do_task_a")
    logger.info("Info message from test_modules.do_task_a")
    logger.warning("Warning message from test_modules.do_task_a")
    logger.error("Error message from test_modules.do_task_a")
    logger.critical("Critical message from test_modules.do_task_a")
    return "Result from task A"


def do_task_b():
    """
    Execute task B with comprehensive logging.

    Demonstrates consistent logging behavior across multiple module functions,
    inheriting the logging threshold from the application configuration.

    Returns:
        str: Task execution result identifier
    """
    logger.debug("Debug message from test_modules.do_task_b")
    logger.info("Info message from test_modules.do_task_b")
    logger.warning("Warning message from test_modules.do_task_b")
    logger.error("Error message from test_modules.do_task_b")
    logger.critical("Critical message from test_modules.do_task_b")
    return "Result from task B"
