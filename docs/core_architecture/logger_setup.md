# Logger Setup - Centralized Logging and Output Control

The `utils/logger_setup.py` module provides a centralized solution for all logging and console output needs in the application. It features a single import approach that provides powerful capabilities including log level control, rich formatting, and automatic suppression of visual output at higher log levels.

## Key Features

- **Single Import**: All functionality is accessed through a single `logger` object
- **Rich Formatting**: Beautiful console output with minimal code
- **Log Level Awareness**: Automatically suppresses non-essential output at ERROR and CRITICAL levels
- **Seamless Integration**: Works with both regular logging and rich console output
- **Smart Print**: Enhances the built-in `print()` function with rich formatting and log level control
- **Automatic Module Detection**: Dynamically creates and routes logs to module-specific loggers
- **Hierarchical Control**: Parent scripts can control log levels of all imported modules

## Basic Usage

```python
from utils.logger_setup import logger

# Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
logger.setLevel("INFO")

# Enable smart print (enhances regular print statements)
logger.enable_smart_print(True)

# Regular logging (always respects log level)
logger.debug("Debug message")  # Only shown at DEBUG level
logger.info("Info message")    # Shown at INFO level and below
logger.warning("Warning")      # Shown at WARNING level and below
logger.error("Error")          # Always shown
logger.critical("Critical")    # Always shown

# Regular print statements (with smart print enabled)
# Shown at DEBUG, INFO, WARNING levels; hidden at ERROR, CRITICAL levels
print("[bold green]This text uses rich formatting[/bold green]")
print("[blue]Blue text[/blue] with [yellow]yellow highlights[/yellow]")

# Critical messages that should always be visible
logger.console.print("[bold red]Always visible regardless of log level[/bold red]")
```

## Smart Print Functionality

When `logger.enable_smart_print(True)` is called, the built-in Python `print()` function is monkey-patched to:

1. Use rich formatting capabilities (colors, styles, tables, panels, etc.)
2. Automatically render rich objects correctly (tables, panels, etc.)
3. Respect log level (shown for DEBUG, INFO, WARNING; hidden for ERROR, CRITICAL)

This allows existing code with print statements to work with our log level control without modification.

### How It Works

```python
# Before enabling smart print
print("This always appears regardless of log level")
print(table)  # May not render rich objects correctly

# After enabling smart print
logger.enable_smart_print(True)

# Now print statements:
# - Are enhanced with rich formatting
# - Properly render rich objects
# - Are suppressed at ERROR and CRITICAL levels
print("[bold]This text is bold[/bold]")
print(table)  # Table renders correctly
```

## Working with Rich Objects

Smart print automatically handles rich objects correctly:

```python
from rich.table import Table
from rich.panel import Panel

# Create a table
table = Table(title="Data")
table.add_column("Name")
table.add_column("Value")
table.add_row("Item 1", "100")
table.add_row("Item 2", "200")

# Just print it - no extra code needed
print(table)  # Renders correctly with smart print enabled

# Create a panel
panel = Panel("Important information", title="Notice")

# Just print it - no extra code needed
print(panel)  # Renders correctly with smart print enabled
```

## Displaying Critical Information

For messages that need to be visible regardless of log level:

```python
# These will always be visible, even at ERROR/CRITICAL levels
logger.console.print("[bold red]Important error details[/bold red]")
logger.console.print("[yellow]Warning that should never be suppressed[/yellow]")
```

## Logger Proxying and Module-Specific Logging

The logger uses a sophisticated proxying mechanism that automatically detects which module is calling it and routes log messages to the appropriate module-specific logger. This provides several key benefits:

1. **Automatic Module Detection**: No need to create or manage separate loggers for each module
2. **Proper Source Module Name**: Log messages show the correct module name without any configuration
3. **Hierarchical Configuration**: Module-specific loggers inherit from the root logger configuration
4. **Module-Level Customization**: Individual modules can have their own log levels

### How Proxying Works

When you call any logging method (`logger.info()`, `logger.debug()`, etc.), the logger automatically:

1. Detects the calling module using runtime introspection
2. Gets or creates a module-specific logger for that module
3. Routes the log message through that module-specific logger
4. Preserves the logger instance for method chaining

This means that logs from different modules will correctly show the source module name:

```python
# In module_a.py
from utils.logger_setup import logger
logger.info("Processing data")  # Shows: INFO module_a: Processing data

# In module_b.py
from utils.logger_setup import logger
logger.info("Handling request")  # Shows: INFO module_b: Handling request
```

### Method Chaining

The proxying mechanism also supports method chaining for more elegant code:

```python
# Multiple log messages in sequence
logger.info("Operation started").debug("Details...").warning("Issues found")

# Configuration and logging
logger.setLevel("DEBUG").show_filename(True).info("Logging configured")
```

### Module-Specific Log Levels

While the root logger level applies to all modules by default, you can set different log levels for specific modules:

```python
# In your main application:
from utils.logger_setup import logger

# Set the root logger level
logger.setLevel("WARNING")  # Only WARNING and above shown by default

# In a specific module that needs more detailed logging:
from utils.logger_setup import logger
import logging

# Set a module-specific log level (only affects this module)
logger.get_logger().setLevel(logging.DEBUG)  # This module will show DEBUG and above
logger.debug("Detailed debug info")  # This will now be visible
```

## Hierarchical Logger Control

One of the most powerful features of the logging system is the ability for a parent script to control the logging behavior of all imported modules. This feature, known as **hierarchical logger control**, is built into Python's logging system and enhanced by our logger implementation.

### How Hierarchical Control Works

1. Python organizes loggers in a hierarchy based on their names (using dots as separators)
2. When you set the log level of a parent logger, it affects all child loggers by default
3. Our `logger.setLevel()` method configures both the root logger and the specific module logger

This means that the main script or entry point can set the overall logging behavior for the entire application, while still allowing specific modules to override if needed:

```python
# In your main.py (the entry point of your application)
from utils.logger_setup import logger

# Set the global log level for ALL modules
logger.setLevel("INFO", configure_root=True)  # Default is True
```

When you do this, several things happen:

1. The root logger's level is set to INFO
2. All existing module loggers are updated to INFO level
3. Any new module loggers created will inherit this level
4. All modules importing and using `logger` will respect this level

This provides centralized control without requiring any special configuration in imported modules.

### Overriding Hierarchical Control

Individual modules can override the inherited log level if needed:

```python
# In a module that needs different logging behavior
from utils.logger_setup import logger

# Override just for this module (doesn't affect other modules)
logger.setLevel("DEBUG", configure_root=False)  # Don't configure root logger
```

### Controlling Print Output Across Modules

The hierarchical control extends to smart print functionality as well. When you enable smart print in your main script, all modules that use regular `print()` statements will respect the global log level:

```python
# In your main.py
from utils.logger_setup import logger

# Set global log level
logger.setLevel("ERROR")

# Enable smart print globally
logger.enable_smart_print(True)

# Import modules that use print statements
import module_a  # Uses print() for non-critical output
import module_b  # Uses print() for non-critical output

# All print statements from module_a and module_b will be suppressed
# since the global log level is ERROR
```

This provides a powerful way to control verbosity across your entire application with a single configuration point.

### Best Practice for Main Scripts

For main scripts or entry points in your application:

```python
from utils.logger_setup import logger

# Configure global logging at the start
logger.setLevel("INFO")        # Set global log level
logger.show_filename(True)     # Show source files in logs
logger.enable_smart_print(True)  # Enable smart print globally

# Import other modules AFTER configuring logging
import module_a
import module_b

# Now all imported modules will respect these settings
```

This establishes a clear control point for logging behavior across your entire application.

## Example Program

This example demonstrates the key features:

```python
#!/usr/bin/env python3
import argparse
from utils.logger_setup import logger
from rich.panel import Panel
from rich.table import Table

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Demo")
    parser.add_argument(
        "--level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set logging level (default: INFO)"
    )
    args = parser.parse_args()

    # Set logging level
    logger.setLevel(args.level)

    # Enable smart print
    logger.enable_smart_print(True)

    # Log some messages
    logger.info(f"Log level set to: {args.level}")
    logger.error("This error message is always visible")

    # Regular print with rich formatting (shown at INFO, hidden at ERROR)
    print("\n[bold green]This text uses rich formatting[/bold green]")

    # Create and print a rich table
    table = Table(title="Data Table Example")
    table.add_column("Name", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Alpha", "100")
    table.add_row("Beta", "200")

    print("\n[bold]Rich Table Example:[/bold]")
    print(table)  # Properly renders at INFO, hidden at ERROR

    # Messages that should always be visible
    logger.console.print("\n[bold red]Important message that's always visible[/bold red]")

if __name__ == "__main__":
    main()
```

## Running the Demo

The repository includes a demo script that demonstrates these features:

```bash
# Run with INFO level (shows all print statements)
python examples/logger_demo/simple_print_demo.py --level INFO

# Run with ERROR level (hides non-essential print statements)
python examples/logger_demo/simple_print_demo.py --level ERROR
```

## Best Practices

1. **Single Import**: Always use `from utils.logger_setup import logger` as the only import
2. **Enable Smart Print**: Call `logger.enable_smart_print(True)` early in your script
3. **Log Levels**: Use appropriate log levels for your messages
   - DEBUG: Detailed debugging information
   - INFO: General information
   - WARNING: Warning messages
   - ERROR: Error messages (always shown)
   - CRITICAL: Critical errors (always shown)
4. **Visual Output**:
   - Use regular `print()` for formatted output that can be suppressed at ERROR level
   - Use `logger.console.print()` for critical information that should always be visible
5. **Rich Objects**: Just `print(rich_object)` directly without extra handling
6. **Hierarchical Control**: Configure logging in main scripts before importing other modules

## Architecture Notes

- The smart print functionality is implemented in the `LoggerProxy` class
- It uses monkey patching to replace the built-in `print()` function
- The implementation leverages the `rich` library for formatting
- A shared console instance is available through `logger.console`
- Log level control uses Python's standard logging module
- The proxying system uses runtime introspection through `inspect.currentframe()` to detect calling modules
- Hierarchical control leverages Python's built-in logger hierarchy to propagate settings

## Working with PCP-PM Demo

The smart print functionality has been integrated into the FCP demo to provide a better user experience:

```python
# Import only logger
from utils.logger_setup import logger

# Enable smart print
logger.enable_smart_print(True)

# Use regular print for formatted output
print(f"[bold green]Configuration:[/bold green]")
print(f"Symbol: {symbol}")
print(f"Market type: {market_type.name}")

# Use logger.console.print for critical information
logger.console.print("[bold red]Error: Unable to retrieve data[/bold red]")
```

This approach simplifies the code while ensuring that:

- Debugging information is shown at lower log levels
- Only critical errors are shown at ERROR and CRITICAL levels
- Rich formatting is consistently applied throughout the output
