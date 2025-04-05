# Logger Implementation

This module provides a streamlined logging implementation with an emphasis on simplicity, hierarchical configuration, and singleton pattern design.

## Core Architecture

The implementation leverages the following design principles:

1. **Hierarchical Logger Configuration**: Propagates configuration from root logger to module-specific loggers
2. **Environment Variable Precedence**: Runtime configuration via `LOG_LEVEL` environment variable supersedes programmatic settings
3. **Proxy Pattern Interface**: Implements lazy module detection via runtime introspection
4. **Method Chaining API**: Supports fluent interface pattern for sequential operations
5. **Singleton Pattern**: Maintains logger instance cache to prevent duplicate configurations
6. **Source File Identification**: Optional filename display to quickly identify log sources

## Usage Patterns

### Module-Level Import (For Component Modules)

```python
from utils.logger_setup import logger

def process_data(dataset):
    """Process data with appropriate logging."""
    logger.debug(f"Processing dataset with {len(dataset)} records")
    logger.info("Data processing initiated")
    logger.warning("Found incomplete records, proceeding with partial data")
    logger.error("Failed to validate output schema")
    logger.critical("System resource exhaustion detected")
```

### Application Entrypoint Configuration

```python
from utils.logger_setup import logger

# Configure logging hierarchy in application entrypoint
logger.setLevel("INFO")  # Sets root logger level

# Optionally enable filename display for better debugging
logger.show_filename(True)  # Shows source filename in log entries

def main():
    logger.info("Application initialization complete")
    logger.warning("Deprecated configuration detected")
    logger.critical("Failed to establish required connections")
```

## Technical Implementation

### Configuration Hierarchy

The logger implements a hierarchical configuration model where:

1. The root logger level establishes the baseline filtering threshold
2. All module-specific loggers inherit from this threshold
3. Environment variables take precedence over programmatic configuration
4. Runtime reconfiguration is possible via the `setLevel()` method

### Logging Levels (Increasing Severity)

1. `DEBUG`: Detailed diagnostic information (development use)
2. `INFO`: Confirmation of expected system behavior
3. `WARNING`: Indication of potential issues or unexpected states
4. `ERROR`: Runtime errors preventing specific operations
5. `CRITICAL`: Critical failures requiring immediate attention

### Runtime Configuration

```python
# Programmatic configuration
logger.setLevel("DEBUG")

# Enable filename display for easier debugging
logger.show_filename(True)

# Environment variable configuration (higher precedence)
# LOG_LEVEL=WARNING python your_application.py
# SHOW_LOG_FILENAME=true python your_application.py
```

### Method Chaining Implementation

The implementation supports the fluent interface pattern via method chaining:

```python
# Configuration chaining
logger.setLevel("INFO").show_filename(True).info("Configuration complete")

# Sequential logging operations
logger.info("Operation started").warning("Anomalies detected").error("Operation failed")
```

### Filename Display Feature

The logger can optionally display source filenames in log messages to help identify where each log is coming from:

```python
# Enable filename display
logger.show_filename(True)
logger.info("This log will show filename and line number")  # Log message with filename at end main.py:10

# Combine with rich logging
logger.use_rich(True).show_filename(True)
logger.info("Rich logging with filename")  # Rich log with filename at end

# Disable filename display
logger.show_filename(False)
logger.info("Back to normal logging without filename")
```

The filename and line number are right-aligned at the end of each log message, creating a clean and consistent layout. This display format aligns filenames in a column at the end of each line, making it easy to scan logs and identify their source without disrupting the main content.

This feature is particularly valuable in larger codebases where understanding the origin of log messages is important for debugging. The implementation uses a custom logger class that properly identifies the actual source file of log messages, rather than displaying the logging infrastructure files.

For example, in a multi-module application:

```python
# main.py
from utils.logger_setup import logger
from user_module import create_user

logger.show_filename(True)
logger.info("Application starting")  # Application starting              main.py:5
create_user("example")  # This will log from user_module.py with correct filename
```

```python
# user_module.py
from utils.logger_setup import logger

def create_user(username):
    logger.info(f"Creating user: {username}")  # Creating user: example      user_module.py:4
```

The logger properly tracks the actual source file and line number regardless of how the logger is accessed through the application, and maintains consistent visual alignment of the log messages.

## Example Implementations

- `test_modules.py`: Demonstrates module-level logger usage without explicit configuration
- `main_example.py`: Illustrates application entrypoint configuration and hierarchical propagation
- `main_example_filename.py`: Shows how to use the filename display feature

## Technical Benefits

- **Runtime Introspection**: Automatically detects calling module context
- **Propagation Mechanics**: Ensures consistent level application throughout logger hierarchy
- **Minimal Configuration Overhead**: Eliminates boilerplate through proxy pattern implementation
- **Thread Safety**: Maintains proper logger isolation across module boundaries
- **Colorized Output**: Leverages ANSI color codes for console output categorization
- **Source Identification**: Optional filename display helps pinpoint log origins
