#!/bin/bash
# Script to build cache from Binance Vision API

# Initialize variables
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"
CSV_FILE="${BASE_DIR}/scripts/binance_vision_api_aws_s3/reports/spot_synchronal.csv"
SYMBOLS=""
INTERVALS="5m"
START_DATE="2025-04-02"
END_DATE=$(date +%Y-%m-%d)
LIMIT=""
LOG_DIR="${BASE_DIR}/logs"
LOG_FILE="${LOG_DIR}/arrow_cache_builder_$(date +%Y%m%d_%H%M%S).log"
MODE="test"  # test or production
TEST_SIZE="small"  # very-small, small, medium (only used in test mode)
SKIP_CHECKSUM=false
PROCEED_ON_CHECKSUM_FAILURE=false
RETRY_FAILED_CHECKSUMS=false
INCREMENTAL_UPDATE=false
FORCE_UPDATE=false
DETECT_GAPS=false
AUTO_MODE=false
ERROR_LOG_FILE=""
# Add new parameters for market type, data provider, and chart type
MARKET_TYPE="spot"
DATA_PROVIDER="BINANCE"
CHART_TYPE="KLINES"

# Create log directory
mkdir -p "$LOG_DIR"

# Function to display usage
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -s, --symbols SYMBOLS      Comma-separated list of symbols (e.g., BTCUSDT,ETHUSDT)"
    echo "  -i, --intervals INTERVALS  Comma-separated list of intervals (default: 5m)"
    echo "  -f, --csv-file FILE        Path to symbols CSV file"
    echo "  -d, --start-date DATE      Start date (YYYY-MM-DD)"
    echo "  -e, --end-date DATE        End date (YYYY-MM-DD)"
    echo "  -l, --limit N              Limit to N symbols"
    echo "  -m, --mode MODE            Mode (test or production)"
    echo "                             test: Small footprint run with preset symbols and intervals"
    echo "                             production: Full run with all symbols from CSV"
    echo "  -t, --test-size SIZE       Test size for test mode (very-small, small, medium)"
    echo "                             very-small: 1 symbol (BTCUSDT), 1 interval (5m), 1 day"
    echo "                             small: 3 symbols, 1 interval (5m), 3 days (default)"
    echo "                             medium: 5 symbols, 2 intervals (5m,1h), 7 days"
    echo "  --skip-checksum            Skip checksum verification entirely"
    echo "  --proceed-on-failure       Proceed with caching even when checksum verification fails"
    echo "  --retry-failed-checksums   Retry downloading files with previously failed checksums"
    echo "  --incremental              Incremental update mode (only download missing data)"
    echo "  --detect-gaps              Detect and fill gaps in the cache"
    echo "  --force-update             Re-download data even if it exists in cache"
    echo "  --auto                     Automatic mode (all symbols, determine dates, fill gaps)"
    echo "  --error-log FILE           Log errors, warnings, and critical messages to specified file"
    echo "  --market-type TYPE         Market type (spot, futures_usdt, futures_coin)"
    echo "  --data-provider PROVIDER   Data provider (default: BINANCE)"
    echo "  --chart-type TYPE          Chart type (default: KLINES)"
    echo "  -h, --help                 Display this help message"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -s|--symbols)
            SYMBOLS="$2"
            shift 2
            ;;
        -i|--intervals)
            INTERVALS="$2"
            shift 2
            ;;
        -f|--csv-file)
            CSV_FILE="$2"
            shift 2
            ;;
        -d|--start-date)
            START_DATE="$2"
            shift 2
            ;;
        -e|--end-date)
            END_DATE="$2"
            shift 2
            ;;
        -l|--limit)
            LIMIT="$2"
            shift 2
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        -t|--test-size)
            TEST_SIZE="$2"
            shift 2
            ;;
        --skip-checksum)
            SKIP_CHECKSUM=true
            shift
            ;;
        --proceed-on-failure)
            PROCEED_ON_CHECKSUM_FAILURE=true
            shift
            ;;
        --retry-failed-checksums)
            RETRY_FAILED_CHECKSUMS=true
            shift
            ;;
        --incremental)
            INCREMENTAL_UPDATE=true
            shift
            ;;
        --detect-gaps)
            DETECT_GAPS=true
            shift
            ;;
        --force-update)
            FORCE_UPDATE=true
            shift
            ;;
        --auto)
            AUTO_MODE=true
            MODE="production"
            INCREMENTAL_UPDATE=true
            DETECT_GAPS=true
            shift
            ;;
        --market-type)
            MARKET_TYPE="$2"
            shift 2
            ;;
        --data-provider)
            DATA_PROVIDER="$2"
            shift 2
            ;;
        --chart-type)
            CHART_TYPE="$2"
            shift 2
            ;;
        --error-log)
            ERROR_LOG_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo "Unknown option: $1"
            usage
            ;;
    esac
done

# Set default mode-specific options
if [ "$MODE" = "test" ]; then
    # Default test mode options based on test size
    if [ -z "$SYMBOLS" ]; then
        case "$TEST_SIZE" in
            very-small)
                SYMBOLS="BTCUSDT"
                INTERVALS="5m"
                # Set date range to just one day
                if [ "$START_DATE" = "2025-04-02" ]; then
                    START_DATE=$(date -d "-1 day" +%Y-%m-%d)
                    END_DATE=$(date +%Y-%m-%d)
                fi
                ;;
            small)
                SYMBOLS="BTCUSDT,ETHUSDT,BNBUSDT"
                INTERVALS="5m"
                # Set date range to three days if not explicitly specified
                if [ "$START_DATE" = "2025-04-02" ]; then
                    START_DATE=$(date -d "-3 days" +%Y-%m-%d)
                    END_DATE=$(date +%Y-%m-%d)
                fi
                ;;
            medium)
                SYMBOLS="BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,ADAUSDT"
                INTERVALS="5m,1h"
                # Set date range to seven days if not explicitly specified
                if [ "$START_DATE" = "2025-04-02" ]; then
                    START_DATE=$(date -d "-7 days" +%Y-%m-%d)
                    END_DATE=$(date +%Y-%m-%d)
                fi
                ;;
            *)
                echo "Invalid test size: $TEST_SIZE. Must be very-small, small, or medium."
                exit 1
                ;;
        esac
    fi
    # Set limit based on test size if not explicitly specified
    if [ -z "$LIMIT" ]; then
        case "$TEST_SIZE" in
            very-small)
                LIMIT="1"
                ;;
            small)
                LIMIT="3"
                ;;
            medium)
                LIMIT="5"
                ;;
        esac
    fi
elif [ "$MODE" = "production" ]; then
    # Default production mode options
    SYMBOLS=""  # Use all symbols from CSV
    INTERVALS=""  # Use all intervals from CSV
    LIMIT=""  # No limit
else
    echo "Invalid mode: $MODE. Must be 'test' or 'production'."
    exit 1
fi

# Only check for CSV file if we need to use it (no symbols provided or in production mode)
USE_CSV=false
if [ -z "$SYMBOLS" ] || [ "$MODE" = "production" ] || [ "$AUTO_MODE" = true ]; then
    USE_CSV=true
    # Check if CSV file exists
    if [ ! -f "$CSV_FILE" ]; then
        echo "CSV file not found: $CSV_FILE"
        exit 1
    fi
fi

# Log setup
echo "=== Arrow Cache Builder Started at $(date) ===" | tee -a "$LOG_FILE"
echo "Mode: $MODE" | tee -a "$LOG_FILE"
if [ "$MODE" = "test" ]; then
    echo "Test Size: $TEST_SIZE" | tee -a "$LOG_FILE"
fi
echo "Symbols: ${SYMBOLS:-'From CSV'}" | tee -a "$LOG_FILE"
echo "Intervals: ${INTERVALS:-'From CSV'}" | tee -a "$LOG_FILE"
echo "Date Range: $START_DATE to $END_DATE" | tee -a "$LOG_FILE"
if [ "$USE_CSV" = true ]; then
    echo "CSV File: $CSV_FILE" | tee -a "$LOG_FILE"
fi
echo "Limit: ${LIMIT:-'No limit'}" | tee -a "$LOG_FILE"
echo "Skip Checksum: $SKIP_CHECKSUM" | tee -a "$LOG_FILE"
echo "Proceed on Checksum Failure: $PROCEED_ON_CHECKSUM_FAILURE" | tee -a "$LOG_FILE"
echo "Retry Failed Checksums: $RETRY_FAILED_CHECKSUMS" | tee -a "$LOG_FILE"
echo "Incremental Update: $INCREMENTAL_UPDATE" | tee -a "$LOG_FILE"
echo "Detect Gaps: $DETECT_GAPS" | tee -a "$LOG_FILE"
echo "Force Update: $FORCE_UPDATE" | tee -a "$LOG_FILE"
echo "Auto Mode: $AUTO_MODE" | tee -a "$LOG_FILE"
echo "Market Type: $MARKET_TYPE" | tee -a "$LOG_FILE"
echo "Data Provider: $DATA_PROVIDER" | tee -a "$LOG_FILE"
echo "Chart Type: $CHART_TYPE" | tee -a "$LOG_FILE"
echo "Error Log File: $ERROR_LOG_FILE" | tee -a "$LOG_FILE"
echo "Log File: $LOG_FILE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Build Python command - always use the synchronous version
PYTHON_CMD="python -m scripts.arrow_cache.cache_builder_sync"

# Add common arguments
if [ -n "$SYMBOLS" ]; then
    PYTHON_CMD="$PYTHON_CMD --symbols $SYMBOLS"
fi

if [ -n "$INTERVALS" ]; then
    PYTHON_CMD="$PYTHON_CMD --intervals $INTERVALS"
fi

PYTHON_CMD="$PYTHON_CMD --start-date $START_DATE --end-date $END_DATE"

# Only add CSV file if we're actually using it
if [ "$USE_CSV" = true ] && [ -n "$CSV_FILE" ]; then
    PYTHON_CMD="$PYTHON_CMD --csv-file $CSV_FILE"
fi

if [ -n "$LIMIT" ]; then
    PYTHON_CMD="$PYTHON_CMD --limit $LIMIT"
fi

# Add checksum options
if [ "$SKIP_CHECKSUM" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --skip-checksum"
fi

if [ "$PROCEED_ON_CHECKSUM_FAILURE" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --proceed-on-checksum-failure"
fi

if [ "$RETRY_FAILED_CHECKSUMS" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --retry-failed-checksums"
fi

# Add incremental update options
if [ "$INCREMENTAL_UPDATE" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --incremental"
fi

if [ "$DETECT_GAPS" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --detect-gaps"
fi

if [ "$FORCE_UPDATE" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --force-update"
fi

if [ "$AUTO_MODE" = true ]; then
    PYTHON_CMD="$PYTHON_CMD --auto"
fi

# Add market parameters
PYTHON_CMD="$PYTHON_CMD --market-type $MARKET_TYPE --data-provider $DATA_PROVIDER --chart-type $CHART_TYPE"

# Add error logging if requested
if [ -n "$ERROR_LOG_FILE" ]; then
    PYTHON_CMD="$PYTHON_CMD --error-log $ERROR_LOG_FILE"
fi

# Add debug flag
PYTHON_CMD="$PYTHON_CMD --debug"

# Log the command
echo "Executing: $PYTHON_CMD" | tee -a "$LOG_FILE"

# Execute Python script
cd "$BASE_DIR" && $PYTHON_CMD 2>&1 | tee -a "$LOG_FILE"

# Check execution status
STATUS=$?
if [ $STATUS -eq 0 ]; then
    echo "Arrow cache building completed successfully!" | tee -a "$LOG_FILE"
else
    echo "Arrow cache building failed with status $STATUS" | tee -a "$LOG_FILE"
fi

# Add after PYTHON_CMD execution
# After the line that runs the Python command but before the if-statement checking $PYTHON_EXIT_CODE
# Add the following line to export the error log environment variable
if [ -n "$ERROR_LOG_FILE" ]; then
    export ERROR_LOG_FILE
fi

echo "=== Arrow Cache Builder Finished at $(date) ===" | tee -a "$LOG_FILE"

exit $STATUS 