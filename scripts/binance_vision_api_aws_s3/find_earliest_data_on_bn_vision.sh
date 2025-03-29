#!/bin/bash

# Script to find the earliest available data for a specified instrument on Binance Vision
# Usage: 
#   1. As standalone: ./find_earliest_data_on_bn_vision.sh [MARKET_TYPE] [SYMBOL] [INTERVAL]
#   2. As library: source find_earliest_data_on_bn_vision.sh; find_earliest_date [MARKET_TYPE] [SYMBOL] [INTERVAL]

#--------------------------------------
# DEFAULT CONFIGURATION
#--------------------------------------
# Only set these values if not already defined (for sourcing compatibility)
MARKET_TYPE="${MARKET_TYPE:-${1:-spot}}"  # Default: spot (options: spot, um, cm)
SYMBOL="${SYMBOL:-${2:-BTCUSDT}}"         # Default: BTCUSDT
INTERVAL="${INTERVAL:-${3:-1s}}"          # Default: 1s (options: 1s, 1m, etc.)
TIMEOUT="${TIMEOUT:-30}"                  # Timeout for each request in seconds
SILENT_MODE="${SILENT_MODE:-false}"       # Silent mode for when script is sourced
DEBUG_MODE="${DEBUG_MODE:-false}"         # Show detailed debugging info
USE_S3="${USE_S3:-true}"                  # Use AWS S3 commands for faster listing (if available)
USE_HTTP_FALLBACK="${USE_HTTP_FALLBACK:-true}" # Use HTTP as fallback if S3 fails

# Get script directory for standardized paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
TEMP_DIR="${LOG_DIR}/temp_find_earliest_data_$$"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# ANSI color codes
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

#--------------------------------------
# UTILITY FUNCTIONS
#--------------------------------------
# Print colored message if not redirected to a file
print_colored() {
    local color="$1"
    local message="$2"
    
    if [ "${SILENT_MODE}" = "true" ]; then
        return
    fi
    
    if [ -t 1 ]; then  # If stdout is a terminal
        echo -e "${color}${message}${NC}"
    else
        echo "${message}"
    fi
}

# Print debug message if DEBUG is enabled
debug_log() {
    if [ "${DEBUG_MODE}" = "true" ] && [ "${SILENT_MODE}" = "false" ]; then
        print_colored "${BLUE}" "[DEBUG] $1" >&2
    fi
}

# Print warning
warn_log() {
    if [ "${SILENT_MODE}" = "false" ]; then
        print_colored "${YELLOW}" "[WARNING] $1" >&2
    fi
}

# Print error
error_log() {
    if [ "${SILENT_MODE}" = "false" ]; then
        print_colored "${RED}" "[ERROR] $1" >&2
    fi
}

# Print success
success_log() {
    if [ "${SILENT_MODE}" = "false" ]; then
        print_colored "${GREEN}" "$1" >&2
    fi
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

#--------------------------------------
# CONSTRUCT FILE URL
#--------------------------------------
construct_file_url() {
    local date=$1
    
    if [ "${MARKET_TYPE}" = "spot" ]; then
        echo "https://data.binance.vision/data/spot/daily/klines/${SYMBOL}/${INTERVAL}/${SYMBOL}-${INTERVAL}-${date}.zip"
    elif [ "${MARKET_TYPE}" = "um" ]; then
        echo "https://data.binance.vision/data/futures/um/daily/klines/${SYMBOL}/${INTERVAL}/${SYMBOL}-${INTERVAL}-${date}.zip"
    elif [ "${MARKET_TYPE}" = "cm" ]; then
        echo "https://data.binance.vision/data/futures/cm/daily/klines/${SYMBOL}/${INTERVAL}/${SYMBOL}-${INTERVAL}-${date}.zip"
    else
        error_log "Invalid market type. Must be 'spot', 'um', or 'cm'."
        return 1
    fi
}

#--------------------------------------
# GET S3 PREFIX
#--------------------------------------
get_s3_prefix() {
    local market_type="$1"
    local symbol="$2"
    local interval="$3"
    
    if [ "${market_type}" = "spot" ]; then
        echo "data/spot/daily/klines/${symbol}/${interval}"
    elif [ "${market_type}" = "um" ]; then
        echo "data/futures/um/daily/klines/${symbol}/${interval}"
    elif [ "${market_type}" = "cm" ]; then
        echo "data/futures/cm/daily/klines/${symbol}/${interval}"
    else
        error_log "Invalid market type. Must be 'spot', 'um', or 'cm'."
        return 1
    fi
}

#--------------------------------------
# CHECK IF DATE EXISTS
#--------------------------------------
check_date_exists() {
    local date=$1
    local url=$(construct_file_url "${date}")
    local status_code=$(curl --write-out "%{http_code}" --silent --output /dev/null --max-time "${TIMEOUT}" "${url}")
    
    if [ "${status_code}" = "200" ] || [ "${status_code}" = "302" ]; then
        return 0  # Date exists
    else
        return 1  # Date doesn't exist
    fi
}

#--------------------------------------
# BINARY SEARCH DATE FUNCTIONS
#--------------------------------------
# Convert date to Unix timestamp
date_to_ts() {
    date -d "$1" +%s 2>/dev/null || date -j -f "%Y-%m-%d" "$1" +%s 2>/dev/null
}

# Convert Unix timestamp to date
ts_to_date() {
    date -d "@$1" +"%Y-%m-%d" 2>/dev/null || date -j -f "%s" "$1" +"%Y-%m-%d" 2>/dev/null
}

# Find the first date in a range where data exists
binary_search_date() {
    local start_date=$1
    local end_date=$2
    local silent=${3:-false}
    
    local start_ts=$(date_to_ts "$start_date")
    local end_ts=$(date_to_ts "$end_date")
    local mid_ts=0
    local mid_date=""
    local found_date=""
    local iterations=0
    
    # If start date has data, it's the earliest
    if check_date_exists "$start_date"; then
        if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
            debug_log "Date $start_date has data - it's our answer!"
        fi
        echo "$start_date"
        return 0
    fi
    
    # If end date doesn't have data, there's no data in the range
    if ! check_date_exists "$end_date"; then
        if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
            debug_log "Date $end_date has no data - no data in this range!"
        fi
        return 1
    fi
    
    # At this point, we know start_date has no data and end_date has data
    # Binary search to find the first date with data
    while [ "$start_ts" -le "$end_ts" ]; do
        mid_ts=$(( (start_ts + end_ts) / 2 ))
        mid_date=$(ts_to_date "$mid_ts")
        ((iterations++))
        
        if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
            debug_log "Testing: $mid_date..."
        else
            if [ "$silent" != "true" ]; then
                echo -n "."  # Show a dot for each iteration
            fi
        fi
        
        if check_date_exists "$mid_date"; then
            if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
                debug_log "FOUND."
            fi
            found_date="$mid_date"
            # Move end point back to find earlier
            end_ts=$(( mid_ts - 86400 )) # 1 day earlier
        else
            if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
                debug_log "Not found."
            fi
            # Move start point forward
            start_ts=$(( mid_ts + 86400 )) # 1 day later
        fi
        
        # If we can't move anymore, we're done
        if [ "$start_ts" -gt "$end_ts" ]; then
            break
        fi
    done
    
    # If no date was found, use end_date
    if [ -z "$found_date" ]; then
        found_date="$end_date"
    fi
    
    # Check one day before the found date to ensure it's truly the first
    local prev_date=$(ts_to_date $(( $(date_to_ts "$found_date") - 86400 )))
    if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
        debug_log "Verifying one day earlier ($prev_date)..."
    else
        if [ "$silent" != "true" ]; then
            echo -n "*"  # Show an asterisk for final verification
        fi
    fi
    
    if check_date_exists "$prev_date"; then
        if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
            debug_log "FOUND! Earlier data exists."
        fi
        found_date="$prev_date"
    else
        if [ "$DEBUG_MODE" = "true" ] && [ "$silent" != "true" ]; then
            debug_log "Not found. We have our answer."
        fi
    fi
    
    if [ "$silent" != "true" ]; then
        if [ "$DEBUG_MODE" = "true" ]; then
            debug_log "Found earliest date $found_date after $iterations iterations."
        else
            echo " Found date: $found_date ($iterations iterations)"
        fi
    fi
    
    echo "$found_date"
    return 0
}

#--------------------------------------
# S3 BASED EARLIEST DATE FINDER
#--------------------------------------
find_earliest_date_s3() {
    local market_type="$1"
    local symbol="$2"
    local interval="$3"
    local silent="${4:-${SILENT_MODE}}"
    local temp_file="${TEMP_DIR}/${market_type}_${symbol}_${interval}_dates.txt"
    
    local bucket="s3://data.binance.vision"
    local prefix=$(get_s3_prefix "$market_type" "$symbol" "$interval")
    
    debug_log "Finding earliest date for ${market_type}/${symbol}/${interval} using AWS S3"
    
    # Create temp directory if it doesn't exist
    mkdir -p "${TEMP_DIR}"
    
    # Check if directory exists
    if ! aws s3 ls --no-sign-request "${bucket}/${prefix}/" > "${temp_file}.raw" 2>/dev/null; then
        debug_log "No data found for ${market_type}/${symbol}/${interval} in S3"
        rm -f "${temp_file}.raw"
        return 1
    fi
    
    # Extract dates from the files and find the earliest one
    # We're looking for the actual zip files, not the checksums
    if ! grep -v "CHECKSUM" "${temp_file}.raw" | \
         grep -o "[0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}" > "${temp_file}"; then
        debug_log "No dates found in S3 listing for ${market_type}/${symbol}/${interval}"
        rm -f "${temp_file}.raw" "${temp_file}"
        return 1
    fi
    
    if [[ ! -s "${temp_file}" ]]; then
        debug_log "Empty dates file for ${market_type}/${symbol}/${interval}"
        rm -f "${temp_file}.raw" "${temp_file}"
        return 1
    fi
    
    local earliest_date=$(sort "${temp_file}" | head -1)
    debug_log "Earliest date for ${market_type}/${symbol}/${interval} from S3: ${earliest_date}"
    
    # Clean up temp files
    rm -f "${temp_file}.raw" "${temp_file}"
    
    # Return the earliest date
    echo "$earliest_date"
    return 0
}

#--------------------------------------
# FIND EARLIEST DATE FUNCTION
#--------------------------------------
find_earliest_date() {
    local market_type="${1:-${MARKET_TYPE}}"
    local symbol="${2:-${SYMBOL}}"
    local interval="${3:-${INTERVAL}}"
    local silent="${SILENT_MODE:-false}"
    
    # Get known launch boundaries for different market types
    local start_date=""
    if [ "$market_type" = "spot" ]; then
        start_date="2017-07-01"  # Binance launched in July 2017
    elif [ "$market_type" = "um" ]; then
        start_date="2019-09-01"  # USDT-M futures launched around Sept 2019
    elif [ "$market_type" = "cm" ]; then
        start_date="2020-09-01"  # Coin-M futures launched around Sept 2020
    else
        error_log "Unknown market type: $market_type"
        return 1
    fi
    
    # End date is today
    local end_date=$(date +"%Y-%m-%d")
    
    if [ "$silent" != "true" ]; then
        echo "Finding earliest available data for $market_type/$symbol/$interval..."
    fi
    
    # Try using AWS S3 method first if enabled
    local earliest_date=""
    local use_s3_method=false
    
    if [ "${USE_S3}" = "true" ] && command_exists aws; then
        if [ "$silent" != "true" ]; then
            echo "Attempting fast S3 listing method..."
        fi
        
        earliest_date=$(find_earliest_date_s3 "$market_type" "$symbol" "$interval" "$silent")
        if [ $? -eq 0 ] && [ -n "$earliest_date" ]; then
            use_s3_method=true
            if [ "$silent" != "true" ]; then
                success_log "Successfully found earliest date using S3: $earliest_date"
            fi
        else
            if [ "$silent" != "true" ] && [ "${USE_HTTP_FALLBACK}" = "true" ]; then
                warn_log "S3 method failed, falling back to HTTP binary search method"
            fi
        fi
    else
        if [ "$silent" != "true" ] && [ "${USE_S3}" = "true" ]; then
            warn_log "AWS CLI not found or S3 method disabled, using HTTP binary search method"
        fi
    fi
    
    # If S3 method failed or is disabled, use HTTP binary search method
    if [ "$use_s3_method" != "true" ] && [ "${USE_HTTP_FALLBACK}" = "true" ]; then
        if [ "$silent" != "true" ]; then
            echo "Searching between $start_date and $end_date using binary search..."
            if [ "$DEBUG_MODE" = "true" ]; then
                echo "Debug mode: ON (showing all tests)"
            else
                echo -n "Progress: "
            fi
        fi
        
        # First, check if there's any data at all by testing the end date
        if ! check_date_exists "$end_date"; then
            # Try a few days earlier in case today's data isn't ready yet
            end_date=$(ts_to_date $(( $(date_to_ts "$end_date") - 86400 )))
            if ! check_date_exists "$end_date"; then
                end_date=$(ts_to_date $(( $(date_to_ts "$end_date") - 86400 )))
                if ! check_date_exists "$end_date"; then
                    if [ "$silent" != "true" ]; then
                        error_log "No data found for $market_type/$symbol/$interval in the recent days."
                    fi
                    echo "Error: No data found"
                    return 1
                fi
            fi
        fi
        
        # Use binary search to find the earliest date
        earliest_date=$(binary_search_date "$start_date" "$end_date" "$silent")
        local result=$?
        
        if [ $result -ne 0 ] || [ -z "$earliest_date" ]; then
            if [ "$silent" != "true" ]; then
                error_log "Could not determine earliest date."
            fi
            echo "Error: No data found"
            return 1
        fi
    fi
    
    if [ "$silent" != "true" ]; then
        echo "----------------------------------------"
        success_log "✅ Earliest available data for $market_type/$symbol/$interval: $earliest_date"
        echo "----------------------------------------"
    fi
    
    echo "$earliest_date"
    
    # Clean up temp directory
    if [ -d "${TEMP_DIR}" ]; then
        rm -rf "${TEMP_DIR}"
    fi
    
    return 0
}

# Function to check if a file exists via HTTP HEAD request
file_exists() {
    local url=$1
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" -I "$url")
    [ "$http_code" -eq 200 ]
}

# Display help information
show_help() {
    echo "Usage: $0 [OPTIONS] [MARKET_TYPE] [SYMBOL] [INTERVAL]"
    echo ""
    echo "Find the earliest available data for a specified instrument on Binance Vision."
    echo ""
    echo "Options:"
    echo "  --help           Show this help message"
    echo "  --debug          Enable debug mode"
    echo "  --silent         Suppress non-essential output"
    echo "  --s3             Use AWS S3 listing method (default: true)"
    echo "  --no-s3          Disable AWS S3 listing method"
    echo "  --http-fallback  Use HTTP as fallback if S3 fails (default: true)"
    echo "  --no-http        Disable HTTP fallback (S3 only)"
    echo ""
    echo "Arguments:"
    echo "  MARKET_TYPE      Market type (spot, um, cm) [default: spot]"
    echo "  SYMBOL           Trading pair symbol [default: BTCUSDT]"
    echo "  INTERVAL         Time interval (1s, 1m, 3m, etc.) [default: 1s]"
    echo ""
    echo "Examples:"
    echo "  $0 spot BTCUSDT 1s              # Find earliest 1s data for BTCUSDT on spot"
    echo "  $0 --debug um ETHUSDT 1h        # Find earliest 1h data with debug info"
    echo "  $0 --no-s3 cm BTCUSD_PERP 1d    # Find earliest data without using S3"
    echo ""
}

# Parse command line arguments
parse_args() {
    local positional=()
    local skip_next=false
    
    for arg in "$@"; do
        if [ "$skip_next" = "true" ]; then
            skip_next=false
            continue
        fi
        
        case "$arg" in
            --help)
                show_help
                exit 0
                ;;
            --debug)
                DEBUG_MODE=true
                ;;
            --silent)
                SILENT_MODE=true
                ;;
            --s3)
                USE_S3=true
                ;;
            --no-s3)
                USE_S3=false
                ;;
            --http-fallback)
                USE_HTTP_FALLBACK=true
                ;;
            --no-http)
                USE_HTTP_FALLBACK=false
                ;;
            *)
                positional+=("$arg")
                ;;
        esac
    done
    
    # Set positional arguments
    if [ ${#positional[@]} -gt 0 ]; then
        MARKET_TYPE=${positional[0]}
    fi
    
    if [ ${#positional[@]} -gt 1 ]; then
        SYMBOL=${positional[1]}
    fi
    
    if [ ${#positional[@]} -gt 2 ]; then
        INTERVAL=${positional[2]}
    fi
}

# If the script is run directly (not sourced), then execute with command line arguments
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    # Parse arguments
    parse_args "$@"
    
    # Run the main function
    find_earliest_date "$MARKET_TYPE" "$SYMBOL" "$INTERVAL"
fi