#!/usr/bin/env python3
"""
Documentation utilities for FCP demo CLI applications.

This module contains functions to generate Markdown documentation from Typer help text.
"""

from pathlib import Path
import typer
import pendulum
import subprocess
import sys
import re
import json
import importlib.util
import shutil
from rich.console import Console
from rich.markdown import Markdown

from utils.logger_setup import logger


def extract_commands_and_options(help_text):
    """Extract commands and options from help text for better formatting.

    Args:
        help_text: The help text from the CLI command

    Returns:
        dict: Dictionary containing extracted sections
    """
    result = {"commands": [], "options": [], "usage": ""}

    # Extract usage
    usage_match = re.search(r"Usage: (.+?)\n", help_text)
    if usage_match:
        result["usage"] = usage_match.group(1).strip()

    # Extract options
    options_section = re.search(r"Options:(.*?)(?:Commands:|$)", help_text, re.DOTALL)
    if options_section:
        options_text = options_section.group(1).strip()
        options_lines = options_text.split("\n")
        current_option = None

        for line in options_lines:
            line = line.strip()
            if line and not line.startswith(" "):
                # This is an option line
                current_option = {
                    "name": line.split("  ")[0].strip(),
                    "description": line.split("  ")[-1].strip() if "  " in line else "",
                }
                result["options"].append(current_option)
            elif current_option and line:
                # This is a continuation of the previous option description
                current_option["description"] += " " + line

    # Extract commands
    commands_section = re.search(r"Commands:(.*?)(?:$)", help_text, re.DOTALL)
    if commands_section:
        commands_text = commands_section.group(1).strip()
        commands_lines = commands_text.split("\n")

        for line in commands_lines:
            line = line.strip()
            if line:
                parts = [p.strip() for p in re.split(r"\s{2,}", line)]
                if len(parts) >= 2:
                    result["commands"].append(
                        {"name": parts[0], "description": parts[1]}
                    )

    return result


def is_typer_cli_available():
    """Check if typer-cli is installed and available."""
    return shutil.which("typer") is not None


def generate_markdown_docs_with_typer_cli(
    app: typer.Typer,
    output_dir: str = "docs/fcp_demo",
    filename: str = "README.md",
    cli_name: str = None,
):
    """Generate Markdown documentation using the typer-cli tool.

    This uses the official Typer CLI tool for better GitHub-friendly docs.

    Args:
        app: The Typer app to generate documentation for
        output_dir: Directory to save the generated documentation
        filename: Name of the output file
        cli_name: The name to use for the CLI app in the docs

    Returns:
        Path: Path to the generated documentation file or None if failed
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / filename

    # Get the script path
    script_path = Path(sys.argv[0]).resolve()

    # If no CLI name is provided, use the script name
    if cli_name is None:
        cli_name = script_path.stem

    try:
        # Use typer utils docs command to first extract the info
        cmd = [
            "typer",
            str(script_path),
            "utils",
            "docs",
            "--name",
            cli_name,
            "--output",
            str(output_file) + ".temp",
        ]

        logger.info(f"Running typer-cli: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            logger.error(f"typer-cli failed: {result.stderr}")
            return None

        # Read the generated file
        temp_file = Path(str(output_file) + ".temp")
        if not temp_file.exists():
            logger.error(f"Expected temporary file not found: {temp_file}")
            return None

        typer_content = temp_file.read_text()

        # Get help text by running the script with --help flag
        try:
            help_result = subprocess.run(
                [str(script_path), "--help"],
                capture_output=True,
                text=True,
                check=False,
            )
            help_text = help_result.stdout.strip()
            if not help_text and help_result.stderr:
                help_text = help_result.stderr.strip()
        except Exception as e:
            logger.warning(f"Could not get help text: {e}")
            help_text = None

        # Create a new GitHub-friendly markdown file
        markdown_content = f"""# {cli_name}: Failover Control Protocol

This CLI tool demonstrates the Failover Control Protocol (FCP) mechanism,
which automatically retrieves Bitcoin data from multiple sources:

1. **Cache** (Local Arrow files)
2. **VISION API**
3. **REST API**

It displays real-time source information about where each data point comes from.

## Time Range Priority Hierarchy

### 1. `--days` or `-d` flag (HIGHEST PRIORITY)

- If provided, overrides any `--start-time` and `--end-time` values
- Calculates range as `[current_time - days, current_time]`
- Example: `--days 5` will fetch data from 5 days ago until now

### 2. `--start-time` and `--end-time` (SECOND PRIORITY)

- Used only when BOTH are provided AND `--days` is NOT provided
- Defines exact time range to fetch data from
- Example: `--start-time 2025-04-10 --end-time 2025-04-15`

### 3. Default Behavior (FALLBACK)

- If neither of the above conditions are met
- Uses default `days=3` to calculate range as `[current_time - 3 days, current_time]`

## Usage

```bash
{cli_name} [OPTIONS]
```

"""

        # Extract options from typer_content
        options_match = re.search(
            r"\*\*Options\*\*:(.*?)(?:\Z|\*\*Commands\*\*:)", typer_content, re.DOTALL
        )
        if options_match:
            options_content = options_match.group(1).strip()
            options_list = re.findall(
                r"\* `([^`]+)`:(.*?)(?=\* |\Z)", options_content, re.DOTALL
            )

            table_header = "| Option | Description |\n|--------|-------------|\n"
            table_rows = []

            for option, description in options_list:
                # Clean up the description
                description = description.strip()

                # Escape pipe characters
                option_escaped = option.replace("|", "\\|")
                description_escaped = description.replace("|", "\\|")

                table_rows.append(f"| `{option_escaped}` | {description_escaped} |")

            options_table = table_header + "\n".join(table_rows)
            markdown_content += f"## Options\n\n{options_table}\n\n"

        # Add examples section
        if help_text:
            # Extract examples from help text if available
            examples_section = """## Examples

### Basic Usage

```bash
./examples/dsm_sync_simple/fcp_demo.py
./examples/dsm_sync_simple/fcp_demo.py --symbol ETHUSDT --market spot
```

### Time Range Options (By Priority)

```bash
# PRIORITY 1: Using --days flag (overrides any start/end times)
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -d 7
  
# PRIORITY 2: Using start and end times (only if --days is NOT provided)
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -st 2025-04-05T00:00:00 -et 2025-04-06T00:00:00
  
# FALLBACK: No time flags (uses default days=3)
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT
```

### Market Types

```bash
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -m um
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSD_PERP -m cm
```

### Different Intervals

```bash
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -i 5m
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -i 1h
./examples/dsm_sync_simple/fcp_demo.py -s SOLUSDT -m spot -i 1s -cc -l D -st 2025-04-14T15:31:01 -et 2025-04-14T15:32:01
```

### Data Source Options

```bash
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -es REST
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -nc
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -cc
```

### Testing FCP Mechanism

```bash
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -fcp
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -fcp -pc
```

### Documentation Generation

```bash
# Generate documentation with typer-cli format (default)
./examples/dsm_sync_simple/fcp_demo.py -gd

# Generate GitHub-optimized documentation
./examples/dsm_sync_simple/fcp_demo.py -gd -df github

# Generate documentation with linting configuration files
./examples/dsm_sync_simple/fcp_demo.py -gd -glc
```

### Combined Examples

```bash
./examples/dsm_sync_simple/fcp_demo.py -s ETHUSDT -m um -i 15m -st 2025-04-01 -et 2025-04-10 -r 5 -l DEBUG
./examples/dsm_sync_simple/fcp_demo.py -s ETHUSD_PERP -m cm -i 5m -d 10 -fcp -pc -l D -cc
```"""

            markdown_content += examples_section

        # Write the final content to the output file
        output_file.write_text(markdown_content + "\n")  # Ensure trailing newline

        # Clean up the temporary file
        if temp_file.exists():
            temp_file.unlink()

        logger.info(f"Generated GitHub-friendly documentation at {output_file}")
        return output_file
    except Exception as e:
        logger.error(f"Error generating GitHub-friendly documentation: {e}")
        return None


def generate_markdown_docs(
    app: typer.Typer,
    output_dir: str = "docs/fcp_demo",
    filename: str = "README.md",
    gen_lint_config: bool = False,
    cli_name: str = None,
):
    """Generate Markdown documentation from a Typer app.

    This function captures the help output from a Typer app and converts it to
    a structured Markdown document optimized for GitHub display.

    It first tries to use the official typer-cli if available, then falls back to
    our custom implementation if typer-cli is not installed.

    Args:
        app: The Typer app to generate documentation for
        output_dir: Directory to save the generated documentation
        filename: Name of the output file
        gen_lint_config: Whether to generate linting configuration files
        cli_name: The name to use for the CLI app in the docs

    Returns:
        Path: Path to the generated documentation file
    """
    # Try to use typer-cli first if it's available (preferred method)
    if is_typer_cli_available():
        logger.info("Found typer-cli, using it for GitHub-friendly documentation")
        result = generate_markdown_docs_with_typer_cli(
            app, output_dir, filename, cli_name=cli_name
        )
        if result:
            # Create linting configuration files if requested
            if gen_lint_config:
                output_path = Path(output_dir)
                # Define the markdownlint configuration with proper Python booleans
                # The json.dumps will convert Python's True/False to JSON true/false
                markdownlint_config = {
                    "MD013": {"code_blocks": False, "tables": False},
                    "MD014": False,  # Disable dollar signs used before commands 
                    "MD040": False,  # Disable requiring language in code blocks
                    "MD047": False   # Disable requiring single newline at end of file
                }
                config_file = output_path / ".markdownlint.json"
                config_file.write_text(json.dumps(markdownlint_config, indent=2))
                logger.info(f"Created markdownlint config at {config_file}")

            # Print success message
            logger.info("Documentation generated successfully using typer-cli")

            # Preview the markdown
            console = Console()
            output_file = Path(output_dir) / filename
            console.print(Markdown(output_file.read_text()))

            return result

    # Fall back to our custom implementation
    logger.info("typer-cli not found, using custom documentation generator")

    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Get the current timestamp
    timestamp = pendulum.now().format("YYYY-MM-DD HH:mm:ss.SSS")

    # Get help text by running the script with --help flag
    script_path = Path(sys.argv[0]).resolve()
    try:
        # Run the script with --help to capture its output
        result = subprocess.run(
            [str(script_path), "--help"],
            capture_output=True,
            text=True,
            check=False,  # Don't raise exception on non-zero exit
        )
        help_text = result.stdout.strip()

        # If stdout is empty, try stderr (some programs output help to stderr)
        if not help_text and result.stderr:
            help_text = result.stderr.strip()

        # If still empty, fall back to a default message
        if not help_text:
            help_text = "Unable to capture help text. Please run the script with --help flag manually."
    except Exception as e:
        logger.error(f"Error capturing help text: {e}")
        help_text = f"Error capturing help text: {e}"

    # Extract structured information from help text
    extracted_info = extract_commands_and_options(help_text)

    # Format CLI options as a table
    options_table = ""
    if extracted_info["options"]:
        options_table = "| Option | Description |\n| ------ | ----------- |\n"
        for opt in extracted_info["options"]:
            # Escape pipe characters in markdown table
            name = opt["name"].replace("|", "\\|")
            description = opt["description"].replace("|", "\\|")
            options_table += f"| `{name}` | {description} |\n"

    # Format commands as a table
    commands_table = ""
    if extracted_info["commands"]:
        commands_table = "| Command | Description |\n| ------- | ----------- |\n"
        for cmd in extracted_info["commands"]:
            # Escape pipe characters in markdown table
            name = cmd["name"].replace("|", "\\|")
            description = cmd["description"].replace("|", "\\|")
            commands_table += f"| `{cmd['name']}` | {cmd['description']} |\n"

    # Check if the help text already includes the "Sample Commands" section
    if "Sample Commands:" in help_text:
        # Don't add additional examples - use the ones from the built-in help
        examples_section = """
## Usage Examples

For convenience, you can generate this documentation using:

```bash
# Generate this documentation
./examples/dsm_sync_simple/fcp_demo.py --gen-doc
./examples/dsm_sync_simple/fcp_demo.py -gd

# Generate documentation with linting configuration files
./examples/dsm_sync_simple/fcp_demo.py -gd -glc
```
"""
    else:
        # If there's no sample commands section in the help text, add our full examples
        examples_section = """
## Examples

Here are some examples of how to use this command:

### Basic Usage

```bash
./examples/dsm_sync_simple/fcp_demo.py
./examples/dsm_sync_simple/fcp_demo.py --symbol ETHUSDT --market spot
```

### Different Time Ranges

```bash
# Using days parameter (highest priority)
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -d 7

# Using explicit start and end times
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -st 2025-04-05T00:00:00 -et 2025-04-06T00:00:00
```

### Market Types

```bash
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSDT -m um
./examples/dsm_sync_simple/fcp_demo.py -s BTCUSD_PERP -m cm
```

### Documentation Generation

```bash
# Generate this documentation
./examples/dsm_sync_simple/fcp_demo.py --gen-doc
./examples/dsm_sync_simple/fcp_demo.py -gd

# Generate documentation with linting configuration files
./examples/dsm_sync_simple/fcp_demo.py -gd -glc
```
"""

    # Format the markdown content with GitHub-friendly structure
    markdown_content = f"""# FCP Demo CLI Documentation

Generated on: {timestamp}

## Overview

This documentation was automatically generated from the Typer CLI help text.

## Usage

```bash
{extracted_info['usage']}
```

## Options

{options_table}

## Commands

{commands_table}

## Original Help Text

<details>
<summary>Click to expand full help text</summary>

```bash
{help_text}
```

</details>
{examples_section}
"""

    # Fix markdown linting issues:
    # 1. Remove multiple consecutive blank lines (MD012)
    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

    # Add an additional cleanup to ensure no trailing multiple blank lines
    markdown_content = markdown_content.rstrip() + "\n"

    # Write to the output file
    output_file = output_path / filename
    output_file.write_text(markdown_content)

    logger.info(f"Generated documentation at {output_file}")

    # Create linting configuration files if requested
    if gen_lint_config:
        # Create a markdownlint config file with customized rules
        markdownlint_config = {
            "MD013": {"code_blocks": False, "tables": False},
            "MD014": False,  # Disable dollar signs used before commands 
            "MD040": False,  # Disable requiring language in code blocks
            "MD047": False   # Disable requiring single newline at end of file
        }

        config_file = output_path / ".markdownlint.json"
        config_file.write_text(json.dumps(markdownlint_config, indent=2))
        logger.info(f"Created markdownlint config at {config_file}")

    # Print the markdown to the console if desired
    console = Console()
    console.print(Markdown(markdown_content))

    return output_file
