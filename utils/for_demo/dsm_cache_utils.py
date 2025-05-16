#!/usr/bin/env python3
"""
Utility functions for managing cache in DSM Demo applications.

This module provides functions for cache directory management and verification
for the Failover Control Protocol (FCP) demonstrations.
"""

import os
import shutil
from pathlib import Path

import platformdirs
from rich import print

from utils.logger_setup import logger

# Get application directories using platformdirs
APP_NAME = "raw-data-services"
APP_AUTHOR = "eon-labs"

# Default cache directory - use platform-specific user cache directory
DEFAULT_CACHE_DIR = Path(platformdirs.user_cache_path(APP_NAME, APP_AUTHOR)) / "dsm-demo"

# Environment variable to override cache location
CACHE_ENV_VAR = "RDS_CACHE_DIR"


def get_cache_dir():
    """Get the cache directory path based on environment or defaults.

    Returns:
        Path: The path to the cache directory
    """
    # Check if environment variable is set
    env_cache_dir = os.environ.get(CACHE_ENV_VAR)
    if env_cache_dir:
        cache_dir = Path(env_cache_dir)
        logger.debug(f"Using cache directory from environment: {cache_dir}")
        return cache_dir

    # Fall back to platform-specific cache directory
    cache_dir = DEFAULT_CACHE_DIR
    logger.debug(f"Using default cache directory: {cache_dir}")
    return cache_dir


def clear_cache_directory(cache_dir=None):
    """Remove the cache directory and its contents.

    Args:
        cache_dir: Path to the cache directory (default: platform-specific cache dir)

    Returns:
        bool: True if operation was successful, False otherwise
    """
    if cache_dir is None:
        cache_dir = get_cache_dir()

    cache_path = Path(cache_dir)
    if cache_path.exists():
        logger.info(f"Clearing cache directory: {cache_path}")
        print(f"[bold yellow]Removing cache directory: {cache_path}[/bold yellow]")
        try:
            shutil.rmtree(cache_path, ignore_errors=True)
            print("[bold green]Cache directory removed successfully[/bold green]")
            return True
        except Exception as e:
            logger.error(f"Error removing cache directory: {e}")
            print(f"[bold red]Error removing cache directory: {e}[/bold red]")
            return False
    else:
        logger.info(f"Cache directory does not exist: {cache_path}")
        print(f"[bold yellow]Cache directory does not exist: {cache_path}[/bold yellow]")
        return False


def ensure_cache_directory(cache_dir=None):
    """Ensure that the cache directory exists.

    Args:
        cache_dir: Path to the cache directory (default: platform-specific cache dir)

    Returns:
        Path: Path object for the created/existing cache directory
    """
    if cache_dir is None:
        cache_dir = get_cache_dir()

    cache_path = Path(cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Ensured cache directory exists: {cache_path}")
    return cache_path


def verify_project_root():
    """Package-aware verification function that always returns True.

    This function exists for backward compatibility but no longer attempts to
    change directories or verify the location, as the package uses platformdirs
    to handle paths correctly regardless of installation method.

    Returns:
        bool: Always returns True
    """
    # Show current working directory in debug logs
    cwd = Path.cwd()
    logger.debug(f"Current working directory: {cwd}")

    # Always return True, no longer checking for specific directories
    return True
