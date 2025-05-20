# Raw Data Service

A high-performance, robust package for efficient market data retrieval from multiple data providers, including [Binance Vision](https://data.binance.vision/) and Binance REST ([Spot](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/general-endpoints), [USDS-Margined Futures](https://developers.binance.com/docs/derivatives/usds-margined-futures/general-info), [Coin-Margined Futures](https://developers.binance.com/docs/derivatives/coin-margined-futures/general-info)) using Apache Arrow MMAP for optimal performance.

## Installation

There are two main ways to install Raw Data Service, depending on your needs:

### 1. For Development or Running Demos Directly

If you want to run the provided demos directly from the cloned repository or use the core library while having the source files available in your workspace, follow these steps:

```bash
# Clone the repository
git clone https://github.com/Eon-Labs/raw-data-services.git
cd raw-data-services

# Install the core package in editable mode
pip install -e .
```

If you plan to contribute to the development, modify the source code, or run tests/linting, include the development dependencies:

```bash
# After cloning and changing directory, install the package with development dependencies
pip install -e ".[dev]"
```

This method keeps all the source files in your workspace and includes necessary tools for development workflows.

### 2. As a Dependency in Your Project (`pyproject.toml`)

If you want to use Raw Data Service as a library in your own Python project (managed with `pyproject.toml`) without including its entire source code in your project's directory, you can add it as a Git dependency.

**Prerequisites:**

- Ensure you have SSH access configured for `github.com`, as this is a private repository. Your SSH key must be authorized to access `Eon-Labs/raw-data-services`.

Add the following to your project's `pyproject.toml` file under the `[project.dependencies]` array (as per PEP 621):

```toml
[project]
# ... other project configurations like name, version ...
dependencies = [
    # ... other dependencies ...
    "raw-data-services @ git+ssh://git@github.com/Eon-Labs/raw-data-services.git"
    # You can also specify a particular branch, tag, or commit hash:
    # "raw-data-services @ git+ssh://git@github.com/Eon-Labs/raw-data-services.git@main"
    # "raw-data-services @ git+ssh://git@github.com/Eon-Labs/raw-data-services.git@v1.0.0"
    # "raw-data-services @ git+ssh://git@github.com/Eon-Labs/raw-data-services.git#egg=raw-data-services" # egg part is good practice
]
```

This will install Raw Data Service into your Python environment's `site-packages` directory, keeping your project workspace clean.

**Note on CLI Tools:**
The installation process (through either method) automatically registers the CLI commands (`dsm-demo-cli` and `dsm-demo-module`) as executable scripts in your Python environment. These commands will be available in your terminal after successful installation.

## Running the Demos

Once installed, you can run the demos using the command-line tools:

### DSM Demo CLI

The CLI demonstration provides an interactive way to explore the Failover Control Protocol:

```bash
# Run the DSM Demo CLI with default parameters
dsm-demo-cli

# Run with specific parameters (get BTC data for a 10-day period)
dsm-demo-cli -s BTCUSDT -i 1m -d 10

# Get help and see all available options
dsm-demo-cli --help
```

The CLI tool will automatically:

1. Check for data in local cache
2. Try to fetch missing data from Binance Vision API
3. Fall back to REST API for data not available in cache or Vision API
4. Save retrieved data to cache for future use

### DSM Demo Module

The module demo provides a programmatic interface:

```bash
# Run the DSM Demo Module to see examples
dsm-demo-module
```

## Using as a Library

The core data fetching functionality of Raw Data Service is available for direct import and use in your Python projects after installation.

The main function for retrieving market data is `fetch_market_data`.

Here's an example of how to use it:

```python
from datetime import datetime
from raw_data_services import fetch_market_data, MarketType, DataProvider, Interval

# Define parameters
provider = DataProvider.BINANCE
market_type = MarketType.SPOT
symbol = "BTCUSDT"
interval = Interval.MINUTE_1
start_time = datetime(2023, 1, 1)
end_time = datetime(2023, 1, 10)

# Fetch data
df, elapsed_time, records_count = fetch_market_data(
    provider=provider,
    market_type=market_type,
    symbol=symbol,
    interval=interval,
    start_time=start_time,
    end_time=end_time,
    use_cache=True,
)

# Process results
print(f"Fetched {records_count} records in {elapsed_time:.2f} seconds")
if df is not None:
    print(df.head())
```

You can import `fetch_market_data` directly from the `raw_data_services` package. The necessary enums (`MarketType`, `DataProvider`, `ChartType`, `Interval`, `DataSource`) and `DataSourceConfig` are also exposed at the top level for easy access.

Refer to the source code of `raw_data_services.core.sync.dsm_lib.fetch_market_data` and `raw_data_services.core.sync.data_source_manager.DataSourceConfig` for detailed parameter information and usage.

## Data Source Manager (DSM) Demo

### Quick Start

- **[DSM Demo CLI Documentation](examples/sync/)**: Interactive demonstration of the Failover Control Protocol mechanism, the core data retrieval strategy that ensures robust and efficient data collection from multiple sources.
- **[DSM Demo Module Documentation](examples/lib_module/)**: Programmatic interface to `core/sync/dsm_lib.py` functions, complementing the CLI tool by providing a library approach to implement the same data retrieval functionality in custom applications.

### Understanding Data Sources

The DSM implements a Failover Control Protocol (FCP) that follows this sequence:

1. **Cache**: First checks local Arrow files for requested data
2. **VISION API**: For missing data, attempts to download from Binance Vision API
3. **REST API**: Falls back to Binance REST API for any remaining data gaps

Note that recent data (within ~48 hours) is typically not available in the Vision API and will be retrieved from the REST API.

## Development Guidelines

### Core Principles

- **[Focus DSM FCP Demo Rule](.cursor/rules/focus-dsm-fcp-demo.mdc)**: The authoritative instruction file guiding the Cursor Agent to strictly adhere to the demo plan and maintain focus on the Failover Control Protocol demonstration.
- [scripts/dev](scripts/dev): Contains various scripts for development and maintenance tasks.

## API Documentation

The `docs/api` folder provides in-depth documentation on data source characteristics and retrieval mechanisms. Refer to the [API Documentation Overview](docs/api/) for a summary of the contents in this directory.

## Data Initialization and Shortlisting

1. Initialization

   - Execute `scripts/binance_vision_api_aws_s3/fetch_binance_data_availability.sh` to build `scripts/binance_vision_api_aws_s3/reports/spot_synchronal.csv`
   - The archaic word _synchronal_ contextually means the Binance Exchanges crypto base pair that we're interested in monitoring, because they must be active in the SPOT, UM and CM market of the Binance Exchange.
   - `scripts/binance_vision_api_aws_s3/reports/spot_synchronal.csv` contains only the Binance SPOT market symbols, their earliest date available, and their available intervals (i.e. 1s, 1m, 3m, ..., 1d), and which base pairs (e.g. BTC) are also on the UM and CM markets.

2. Shortlisting

   - To exclude specific symbols from subsequent operations below, simply remove their corresponding lines from `spot_synchronal.csv`

## Development Scripts

The `scripts/dev` directory contains a collection of utility scripts designed to assist with various development, testing, and maintenance tasks. These scripts leverage modern Python tooling and practices to streamline workflows.

Some of the key tools and libraries used across these scripts include:

- **Ruff**: For fast linting and code formatting.
- **Vulture**: To identify dead code.
- **pytest-xdist**: For parallel test execution.
- **rope**: For Python code refactoring, used in conjunction with `git mv` for moving files.
- **fsspec**: For seamless interaction with various filesystems.

Explore the scripts and their individual READMEs within the [`scripts/dev`](scripts/dev) directory for more details.
