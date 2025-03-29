#!/bin/bash

###########################################
# User Configuration - Edit values below
###########################################

#--------------------------------------
# DATA SOURCE CONFIGURATION
#--------------------------------------
# Market Type:
# - "spot" - Spot Market (all intervals available, 1s and all others)
# - "um"   - USDT-Margined Futures (all intervals except 1s, earliest ~2019-12-31 for BTCUSDT)
# - "cm"   - Coin-Margined Futures (all intervals except 1s, symbols have _PERP suffix, earliest ~2020-09-23 for BCHUSD_PERP)
MARKET_TYPE="spot"

# Trading pair to process
# - For SPOT and UM: typically like "BTCUSDT", "ETHUSDT", etc.
# - For CM: typically like "BTCUSD_PERP", "ETHUSD_PERP" or "BCHUSD_PERP", etc.
# For multiple symbols, use space-separated list: "BTCUSDT ETHUSDT XRPUSDT"
SYMBOLS="BTCUSDT ETHUSDT BNBUSDT LTCUSDT ADAUSDT XRPUSDT EOSUSDT XLMUSDT TRXUSDT ETCUSDT ICXUSDT VETUSDT LINKUSDT ZILUSDT XMRUSDT THETAUSDT MATICUSDT ATOMUSDT FTMUSDT ALGOUSDT DOGEUSDT CHZUSDT XTZUSDT BCHUSDT KNCUSDT MANAUSDT SOLUSDT SANDUSDT CRVUSDT DOTUSDT LUNAUSDT EGLDUSDT RUNEUSDT UNIUSDT AVAXUSDT NEARUSDT AAVEUSDT FILUSDT AXSUSDT ROSEUSDT GALAUSDT ENSUSDT GMTUSDT APEUSDT OPUSDT APTUSDT SUIUSDT WLDUSDT WIFUSDT DOGSUSDT"

# Time intervals to process (space-separated list)
# Available intervals:
# - "1s" (SPOT only)
# - "1m", "3m", "5m", "15m", "30m"
# - "1h", "2h", "4h", "6h", "8h", "12h"
# - "1d"
INTERVALS="1s 1m 3m 5m 15m 30m 1h 2h 4h 6h 8h 12h 1d"

# Test mode - process a shorter date range for testing
TEST_MODE=false

# Date range to process
if [ "$TEST_MODE" = true ]; then
    # Test mode - just process 3 days of data to be faster
    START_DATE=$(date -d "3 days ago" +"%Y-%m-%d" 2>/dev/null || date -j -v-3d +"%Y-%m-%d" 2>/dev/null)
    END_DATE=$(date -d "5 days ago" +"%Y-%m-%d" 2>/dev/null || date -j -v-5d +"%Y-%m-%d" 2>/dev/null)
    START_DATE_AUTO=true     # Auto-detect latest available date
    END_DATE_AUTO=false      # Use fixed end date for faster testing
else
    # Full mode - process all available data
    START_DATE="2025-03-27"  # Start date (YYYY-MM-DD) - Not used when START_DATE_AUTO=true
    END_DATE="2025-03-20"    # End date (YYYY-MM-DD) - Not used when END_DATE_AUTO=true
    START_DATE_AUTO=true     # Set to true to automatically find the latest available date
    END_DATE_AUTO=true       # Set to true to automatically find the earliest available date
fi

#--------------------------------------
# RUN IDENTIFICATION
#--------------------------------------
RUN_LABEL="initial"     # User-defined label for this run (e.g., "initial", "retry1", "full")
RETRY_FROM=""           # Path to CSV file to retry from (empty for fresh run)

#--------------------------------------
# PERFORMANCE CONFIGURATION
#--------------------------------------
MAX_PARALLEL=50          # Number of parallel processes (lower for testing, increase for production)
ARIA_CONNECTIONS=1       # Number of connections per download
DOWNLOAD_TIMEOUT=30      # Download timeout in seconds
MAX_RETRIES=3            # Maximum number of download retries

#--------------------------------------
# OUTPUT CONFIGURATION
#--------------------------------------
SAVE_FAILURES=true      # Whether to save failed downloads separately
SHOW_PROGRESS=true      # Whether to show progress dots
SHOW_DATES=false        # Whether to show the list of dates being processed

###########################################
# Script Configuration - Do not edit below
###########################################

# Common variables
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
TEMP_DIR="${LOG_DIR}/temp_$(date +%Y%m%d_%H%M%S)"
RESULTS_DIR="${TEMP_DIR}/results"

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"

# Validate intervals and set expected lines per interval
VALID_INTERVALS=("1s" "1m" "3m" "5m" "15m" "30m" "1h" "2h" "4h" "6h" "8h" "12h" "1d")
SPOT_VALID_INTERVALS=("1s" "1m" "3m" "5m" "15m" "30m" "1h" "2h" "4h" "6h" "8h" "12h" "1d")
UM_CM_VALID_INTERVALS=("1m" "3m" "5m" "15m" "30m" "1h" "2h" "4h" "6h" "8h" "12h" "1d")

# Function to get expected line count for an interval
get_expected_lines() {
    local interval=$1
    
    case "${interval}" in
        "1s")  echo 86400 ;;   # 60 * 60 * 24
        "1m")  echo 1440 ;;    # 60 * 24
        "3m")  echo 480 ;;     # 60 * 24 / 3
        "5m")  echo 288 ;;     # 60 * 24 / 5
        "15m") echo 96 ;;      # 60 * 24 / 15
        "30m") echo 48 ;;      # 60 * 24 / 30
        "1h")  echo 24 ;;      # 24
        "2h")  echo 12 ;;      # 24 / 2
        "4h")  echo 6 ;;       # 24 / 4
        "6h")  echo 4 ;;       # 24 / 6
        "8h")  echo 3 ;;       # 24 / 8
        "12h") echo 2 ;;       # 24 / 12
        "1d")  echo 1 ;;       # 1
        *)     echo 0 ;;       # Unknown interval
    esac
}

# Function to get base URL for a market type
get_base_url() {
    local market=$1
    local symbol=$2
    
    if [ "${market}" = "spot" ]; then
        echo "https://data.binance.vision/data/spot/daily/klines/${symbol}"
    elif [ "${market}" = "um" ]; then
        echo "https://data.binance.vision/data/futures/um/daily/klines/${symbol}"
    elif [ "${market}" = "cm" ]; then
        echo "https://data.binance.vision/data/futures/cm/daily/klines/${symbol}"
    else
        echo "Error: Invalid market type. Must be 'spot', 'um', or 'cm'." >&2
        return 1
    fi
}

# Function to get the URL for a specific date
get_file_url() {
    local base_url=$1
    local interval=$2
    local date=$3
    local suffix=${4:-}

    echo "${base_url}/${interval}/${SYMBOL}-${interval}-${date}.zip${suffix}"
}

# Function to check if a file exists via HTTP
check_file_exists() {
    local url=$1
    local status_code=$(curl -s -o /dev/null -w "%{http_code}" -I "${url}")
    
    if [ "${status_code}" = "200" ] || [ "${status_code}" = "302" ]; then
        return 0  # Success
    else
        return 1  # Failure
    fi
}

# Function to handle date manipulation (compatible with BSD and GNU date)
adjust_date() {
    local input_date=$1
    local days_offset=$2
    
    date -d "${input_date} ${days_offset} days" +"%Y-%m-%d" 2>/dev/null || \
    date -j -v"${days_offset}d" -f "%Y-%m-%d" "${input_date}" +"%Y-%m-%d" 2>/dev/null
}

# Validate intervals based on market type
validate_intervals() {
    local market=$1
    local intervals_to_check=$2
    
    local valid_list
    if [ "${market}" = "spot" ]; then
        valid_list=("${SPOT_VALID_INTERVALS[@]}")
    else
        valid_list=("${UM_CM_VALID_INTERVALS[@]}")
    fi
    
    local validated_intervals=()
    for interval in ${intervals_to_check}; do
        local is_valid=false
        for valid_interval in "${valid_list[@]}"; do
            if [ "${interval}" = "${valid_interval}" ]; then
                is_valid=true
                break
            fi
        done
        
        if [ "${is_valid}" = true ]; then
            validated_intervals+=("${interval}")
        else
            echo "Warning: Interval '${interval}' is not valid for ${market} market, skipping." >&2
        fi
    done
    
    # Return space-separated list of validated intervals
    echo "${validated_intervals[@]}"
}

# Auto-detect the latest date for START_DATE if START_DATE_AUTO is true
auto_detect_latest_date() {
    local market_type=$1
    local symbol=$2
    local interval=$3
    local default_date=$4
    
    echo "Auto-detecting the latest available date for ${market_type}/${symbol}/${interval}..." >&2
    
    # Get base URL
    local base_url=$(get_base_url "${market_type}" "${symbol}")
    
    # Start from today and search backward up to 10 days
    local current_date=$(date +"%Y-%m-%d")
    local max_days_back=10
    
    echo -n "Checking dates: " >&2
    
    for days_back in $(seq 0 ${max_days_back}); do
        # Calculate the date to check
        local check_date=""
        if [ ${days_back} -eq 0 ]; then
            check_date="${current_date}"
        else
            # Use direct date command with the specific format needed
            check_date=$(date -d "${current_date} -${days_back} days" +"%Y-%m-%d" 2>/dev/null || date -j -v-${days_back}d -f "%Y-%m-%d" "${current_date}" +"%Y-%m-%d" 2>/dev/null)
        fi
        
        echo -n "${check_date} " >&2
        
        # Use direct curl command
        local filename="${symbol}-${interval}-${check_date}.zip"
        local url="${base_url}/${interval}/${filename}"
        local status=$(curl -s -o /dev/null -w "%{http_code}" -I "${url}")
        
        if [ "${status}" = "200" ] || [ "${status}" = "302" ]; then
            echo "" >&2
            echo "✅ Found latest available date: ${check_date}" >&2
            echo "${check_date}"
            return 0
        fi
        
        echo -n "→ " >&2
    done
    
    echo "" >&2
    echo "⚠️ Could not find recent data within last ${max_days_back} days. Using default START_DATE: ${default_date}" >&2
    echo "${default_date}"
    return 1
}

# Auto-detect the earliest date if END_DATE_AUTO is true
find_earliest_date() {
    local market_type=$1
    local symbol=$2
    local interval=$3
    
    echo "Auto-detecting the earliest available date for ${market_type}/${symbol}/${interval}..." >&2
    
    # Check if the earliest date finder script exists
    if [ ! -f "${SCRIPT_DIR}/find_earliest_data_on_bn_vision.sh" ]; then
        echo "Error: find_earliest_data_on_bn_vision.sh script not found!" >&2
        return 1
    fi
    
    # Run the finder script to get the earliest date with S3 optimization
    # Show dots for progress but keep output clean
    local earliest_date=$(bash "${SCRIPT_DIR}/find_earliest_data_on_bn_vision.sh" "${market_type}" "${symbol}" "${interval}" "--s3" "--silent" | tail -n 1)
    
    # Check if earliest date was found successfully
    if [ -z "${earliest_date}" ] || [[ "${earliest_date}" == *"Error"* ]]; then
        echo "Error: Could not determine the earliest date for ${market_type}/${symbol}/${interval}" >&2
        return 1
    fi
    
    # Return the found earliest date
    echo "${earliest_date}"
}

# Function to generate standardized file names
get_file_names() {
    local symbol=$1
    local interval=$2
    local start_date=$3
    local end_date=$4
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local base_name="${MARKET_TYPE}_${symbol}_${interval}_${start_date}_to_${end_date}"
    local retry_info=""
    
    # If this is a retry run, add information about which file we're retrying from
    if [ -n "${RETRY_FROM}" ]; then
        # Extract the run label from the original file
        local original_label=$(basename "${RETRY_FROM}" | sed -E 's/.*_([^_]+)_[0-9]{8}_[0-9]{6}(_.*)?.csv/\1/')
        retry_info="_retry_from_${original_label}"
    fi
    
    echo "${LOG_DIR}/${base_name}_${RUN_LABEL}${retry_info}_${timestamp}.csv"
}

# Function to get HTTP headers
get_http_headers() {
    local url=$1
    local headers_file=$2
    
    curl -sI "${url}" > "${headers_file}"
    
    # Extract header information
    local last_modified=$(grep -i "last-modified:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n' || echo "NA")
    local etag=$(grep -i "etag:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n"' || echo "NA")
    local server=$(grep -i "server:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n' || echo "NA")
    local content_type=$(grep -i "content-type:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n' || echo "NA")
    local content_length=$(grep -i "content-length:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n' || echo "NA")
    local x_cache=$(grep -i "x-cache:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n' || echo "NA")
    local x_amz_cf_id=$(grep -i "x-amz-cf-id:" "${headers_file}" | cut -d' ' -f2- | tr -d '\r\n' || echo "NA")
    
    echo "$last_modified,$etag,$server,$content_type,$content_length,$x_cache,$x_amz_cf_id"
}

# Function to download file with aria2
download_file() {
    local url=$1
    local output_file=$2
    local connections=$3
    local timeout=$4
    local retries=$5
    
    aria2c --quiet --max-connection-per-server="${connections}" \
           --connect-timeout="${timeout}" --timeout="${timeout}" --max-tries="${retries}" \
           --allow-overwrite=true \
           --auto-file-renaming=false \
           --out="${output_file}" "${url}"
    
    return $?
}

# Function to show progress indicator
show_progress() {
    local status=$1
    
    if [ "${SHOW_PROGRESS}" = true ]; then
        if [ "${status}" = "success" ]; then
            echo -n "."
        elif [ "${status}" = "failure" ]; then
            echo -n "!"
        elif [ "${status}" = "unzip_error" ]; then
            echo -n "x"
        fi
    fi
}

# Function to create result line
create_result_line() {
    local checksum_match=$1
    local date=$2
    local interval=$3
    local expected_checksum=$4
    local actual_checksum=$5
    local file_size=$6
    local line_count=$7
    local unique_timestamps=$8
    local first_timestamp=$9
    local last_timestamp=${10}
    local http_status=${11}
    local headers=${12}
    
    echo "${checksum_match},${date},${interval},${expected_checksum},${actual_checksum},${file_size},${line_count},${unique_timestamps},${first_timestamp},${last_timestamp},${http_status},${headers}"
}

# Function to efficiently remove directories (faster than rm -rf for large directories)
fast_remove_dir() {
    local dir_to_remove=$1
    
    # Check if directory exists
    if [ ! -d "${dir_to_remove}" ]; then
        return 0
    fi
    
    # Check if rsync is available
    if command -v rsync >/dev/null 2>&1; then
        # Create empty temp directory
        local empty_dir=$(mktemp -d)
        
        # Use rsync to efficiently delete by syncing with empty directory
        rsync -a --delete "${empty_dir}/" "${dir_to_remove}/"
        
        # Remove the now-empty directory and temp directory
        rmdir "${dir_to_remove}" "${empty_dir}"
    else
        # Fall back to rm if rsync is not available
        rm -rf "${dir_to_remove}"
    fi
}

# Function to analyze a file and write to temp file
analyze_file() {
    local date=$1
    local interval=$2
    local index=$3
    local symbol=$4
    local result_file="${RESULTS_DIR}/${symbol}_${interval}_${index}.csv"
    local url_date=$(date -d "${date}" +"%Y-%m-%d" 2>/dev/null || date -j -f "%Y-%m-%d" "${date}" +"%Y-%m-%d" 2>/dev/null)
    local filename="${symbol}-${interval}-${url_date}.zip"
    local checksum_file="${filename}.CHECKSUM"
    local base_url=$(get_base_url "${MARKET_TYPE}" "${symbol}")
    local url="${base_url}/${interval}/${filename}"
    local checksum_url="${url}.CHECKSUM"
    local work_dir="${TEMP_DIR}/work_${symbol}_${interval}_${date}"
    local expected_lines=$(get_expected_lines "${interval}")
    
    # Create work directory
    fast_remove_dir "${work_dir}"  # Clean up any existing directory
    mkdir -p "${work_dir}"
    chmod 777 "${work_dir}"
    
    # Change to work directory
    pushd "${work_dir}" > /dev/null || {
        echo "0,${date},${interval},DIR_ERROR,DIR_ERROR,0,0,0,,,500,NA,NA,NA,NA,NA,NA,NA" > "${result_file}"
        return 1
    }
    
    # First check if the file exists and get headers
    local headers_file="${work_dir}/headers.txt"
    local header_values="NA,NA,NA,NA,NA,NA,NA" # Default values
    
    if ! curl -sI "${url}" > "${headers_file}"; then
        echo "0,${date},${interval},NOT_FOUND,NOT_FOUND,0,0,0,,,404,${header_values}" > "${result_file}"
        popd > /dev/null
        fast_remove_dir "${work_dir}"
        show_progress "failure"
        return 0
    fi
    
    # Extract HTTP headers
    header_values=$(get_http_headers "${url}" "${headers_file}")
    
    # Download files with aria2
    if ! download_file "${url}" "${filename}" "${ARIA_CONNECTIONS}" "${DOWNLOAD_TIMEOUT}" "${MAX_RETRIES}" || \
       ! download_file "${checksum_url}" "${checksum_file}" "${ARIA_CONNECTIONS}" "${DOWNLOAD_TIMEOUT}" "${MAX_RETRIES}"; then
        echo "0,${date},${interval},DOWNLOAD_FAILED,DOWNLOAD_FAILED,0,0,0,,,500,${header_values}" > "${result_file}"
        popd > /dev/null
        fast_remove_dir "${work_dir}"
        show_progress "failure"
        return 0
    fi
    
    # Check if both files exist
    if [ ! -f "${filename}" ] || [ ! -f "${checksum_file}" ]; then
        echo "0,${date},${interval},FILE_MISSING,FILE_MISSING,0,0,0,,,404,${header_values}" > "${result_file}"
        popd > /dev/null
        fast_remove_dir "${work_dir}"
        show_progress "failure"
        return 0
    fi
    
    # Calculate actual checksum
    local actual_checksum=$(sha256sum "${filename}" | cut -d' ' -f1)
    
    # Read expected checksum
    local expected_checksum=""
    if [ -f "${checksum_file}" ]; then
        expected_checksum=$(tr -d ' \r' < "${checksum_file}" | sed "s/${filename}\$//")
    fi
    
    # Check if checksums match
    local checksum_match=0
    if [ -n "${expected_checksum}" ] && [ "${actual_checksum}" = "${expected_checksum}" ]; then
        checksum_match=1
    fi
    
    # Get file size
    local file_size=0
    if [ -f "${filename}" ]; then
        file_size=$(ls -l "${filename}" | awk '{print $5}')
    fi
    
    # Extract and analyze data
    local temp_csv="${work_dir}/temp.csv"
    if ! unzip -p "${filename}" > "${temp_csv}" 2>/dev/null; then
        echo "0,${date},${interval},UNZIP_FAILED,${actual_checksum},${file_size},0,0,,,200,${header_values}" > "${result_file}"
        popd > /dev/null
        fast_remove_dir "${work_dir}"
        show_progress "unzip_error"
        return 0
    fi
    
    # Count lines and unique timestamps
    local line_count=0
    local unique_timestamps=0
    local first_timestamp=""
    local last_timestamp=""
    
    if [ -f "${temp_csv}" ]; then
        line_count=$(wc -l < "${temp_csv}")
        unique_timestamps=$(cut -d',' -f1 "${temp_csv}" | sort -u | wc -l)
        first_timestamp=$(head -n1 "${temp_csv}" | cut -d',' -f1)
        last_timestamp=$(tail -n1 "${temp_csv}" | cut -d',' -f1)
    fi
    
    # Write results to result file
    echo "${checksum_match},${date},${interval},${expected_checksum},${actual_checksum},${file_size},${line_count},${unique_timestamps},${first_timestamp},${last_timestamp},200,${header_values}" > "${result_file}"
    
    # Clean up
    popd > /dev/null
    fast_remove_dir "${work_dir}"
    
    # Show progress
    if [ "${checksum_match}" = "1" ]; then
        show_progress "success"
    else
        show_progress "failure"
    fi
}

# Function to get all dates between start and end
get_date_range() {
    local start_date=$1
    local end_date=$2
    local current_date=$start_date
    
    # Process dates from start_date down to end_date
    while [ "$(date -d "$current_date" +%s)" -ge "$(date -d "$end_date" +%s)" ]; do
        echo "$current_date"
        current_date=$(adjust_date "$current_date" "-1")
    done
}

# Function to extract failed dates from CSV
get_failed_dates() {
    local csv_file=$1
    local interval=$2
    
    # Skip header, get dates where checksum_match is 0 and interval matches
    if [ -n "${interval}" ]; then
        tail -n +2 "${csv_file}" | awk -F',' "\$1 == \"0\" && \$3 == \"${interval}\" {print \$2}"
    else
        tail -n +2 "${csv_file}" | awk -F',' '$1 == "0" {print $2","$3}'
    fi
}

# Function to process dates for a specific interval
process_interval() {
    local interval=$1
    local start_date=$2
    local end_date=$3
    local symbol=$4
    
    # Get expected line count for this interval
    local expected_line_count=$(get_expected_lines "${interval}")
    echo "Processing ${symbol} - ${interval} data (${expected_line_count} expected lines per file)"
    
    # If auto-detect is enabled for this interval, detect latest date
    if [ "${START_DATE_AUTO}" = true ]; then
        local auto_start=$(auto_detect_latest_date "${MARKET_TYPE}" "${symbol}" "${interval}" "${start_date}" | tail -n 1)
        if [ -n "${auto_start}" ]; then
            start_date="${auto_start}"
        fi
    fi
    
    # If auto-detect for earliest date is enabled, detect earliest date
    if [ "${END_DATE_AUTO}" = true ]; then
        local auto_end=$(find_earliest_date "${MARKET_TYPE}" "${symbol}" "${interval}")
        if [ -n "${auto_end}" ]; then
            end_date="${auto_end}"
        fi
    fi
    
    echo "Date range for ${symbol} - ${interval}: ${start_date} to ${end_date}"
    
    # Create main CSV file for this interval
    local main_csv=$(get_file_names "${symbol}" "${interval}" "${start_date}" "${end_date}")
    local failed_csv="${main_csv%.csv}_failed.csv"
    
    # Create CSV header
    echo "checksum_match,date,interval,expected_checksum,actual_checksum,file_size,line_count,unique_timestamps,first_timestamp,last_timestamp,http_status,last_modified,etag,server,content_type,content_length,x_cache,x_amz_cf_id" > "${main_csv}"
    chmod 666 "${main_csv}"  # Ensure file is writable
    
    if [ "${SAVE_FAILURES}" = true ]; then
        echo "checksum_match,date,interval,expected_checksum,actual_checksum,file_size,line_count,unique_timestamps,first_timestamp,last_timestamp,http_status,last_modified,etag,server,content_type,content_length,x_cache,x_amz_cf_id" > "${failed_csv}"
    fi
    
    # Get all dates to process
    local dates=()
    if [ "${RETRY_MODE}" = true ]; then
        # Get failed dates for this interval from the retry file
        mapfile -t dates < <(get_failed_dates "${RETRY_FROM}" "${interval}")
        if [ ${#dates[@]} -eq 0 ]; then
            echo "No failed downloads found for ${interval} in ${RETRY_FROM}"
            return 0
        fi
    else
        # Get all dates in the specified range
        mapfile -t dates < <(get_date_range "${start_date}" "${end_date}")
    fi
    
    if [ "${SHOW_DATES}" = true ]; then
        echo "Number of dates to process for ${symbol} - ${interval}: ${#dates[@]}"
        echo "Dates to process:"
        printf '%s\n' "${dates[@]}"
        echo "----------------------------------------"
    fi
    
    echo "Results will be saved to: $(basename "${main_csv}")"
    
    if [ "${SHOW_PROGRESS}" = true ]; then
        echo -n "Progress for ${symbol} - ${interval}: "
    fi
    
    # Process dates in parallel with controlled concurrency
    index=0
    for date in "${dates[@]}"; do
        # Wait if we've reached max parallel processes
        while [ $(jobs -r | wc -l) -ge ${MAX_PARALLEL} ]; do
            sleep 1
        done
        
        # Start a new background process
        analyze_file "$date" "${interval}" "$index" "${symbol}" &
        
        ((index++))
    done
    
    # Wait for all background jobs to complete
    wait
    
    # Combine results in order
    for i in $(seq 0 $((index-1))); do
        if [ -f "${RESULTS_DIR}/${symbol}_${interval}_${i}.csv" ]; then
            # Add to main results file
            cat "${RESULTS_DIR}/${symbol}_${interval}_${i}.csv" >> "${main_csv}"
            
            # If checksum_match is 0 and failures saving is enabled, add to failures file
            if [ "${SAVE_FAILURES}" = true ] && grep -q "^0," "${RESULTS_DIR}/${symbol}_${interval}_${i}.csv"; then
                cat "${RESULTS_DIR}/${symbol}_${interval}_${i}.csv" >> "${failed_csv}"
            fi
        fi
    done
    
    if [ "${SHOW_PROGRESS}" = true ]; then
        echo  # New line after progress dots
    fi
    
    echo "Completed processing ${symbol} - ${interval}. Results saved to: ${main_csv}"
    if [ "${SAVE_FAILURES}" = true ]; then
        local failure_count=$(wc -l < "${failed_csv}")
        if [ "${failure_count}" -gt 1 ]; then  # More than just the header line
            # Rename failed file with the actual date range of the failed entries
            local failed_earliest=$(tail -n +2 "${failed_csv}" | sort -t',' -k2 | head -n1 | cut -d',' -f2)
            local failed_latest=$(tail -n +2 "${failed_csv}" | sort -t',' -k2 | tail -n1 | cut -d',' -f2)
            
            if [ -n "${failed_earliest}" ] && [ -n "${failed_latest}" ]; then
                local timestamp=$(date +%Y%m%d_%H%M%S)
                local new_failed_name="${LOG_DIR}/${MARKET_TYPE}_${symbol}_${interval}_${failed_latest}_to_${failed_earliest}_${RUN_LABEL}_failed_${timestamp}.csv"
                mv "${failed_csv}" "${new_failed_name}"
                echo "Failed downloads for ${symbol} - ${interval} saved to: $(basename "${new_failed_name}")"
            else
                echo "Failed downloads for ${symbol} - ${interval} saved to: $(basename "${failed_csv}")"
            fi
        else
            echo "No failures detected for ${symbol} - ${interval}! All files processed successfully."
            rm -f "${failed_csv}"  # Remove empty failures file
        fi
    fi
    
    echo "----------------------------------------"
}

# Create directories if they don't exist
mkdir -p "${LOG_DIR}" "${RESULTS_DIR}"
chmod 777 "${LOG_DIR}" "${RESULTS_DIR}"

# Set retry mode flag
RETRY_MODE=false
if [ -n "${RETRY_FROM}" ]; then
    RETRY_MODE=true
    if [ ! -f "${RETRY_FROM}" ]; then
        echo "Error: Retry file ${RETRY_FROM} not found."
        exit 1
    fi
    echo "Retry mode: Processing failed downloads from ${RETRY_FROM}"
fi

# Validate intervals against market type
VALIDATED_INTERVALS=$(validate_intervals "${MARKET_TYPE}" "${INTERVALS}")

if [ -z "${VALIDATED_INTERVALS}" ]; then
    echo "Error: No valid intervals to process for ${MARKET_TYPE} market."
    exit 1
fi

echo "=========================================="
echo " Multi-Symbol & Interval Verification Tool"
echo "=========================================="
echo "Market: ${MARKET_TYPE}"
echo "Symbols: ${SYMBOLS}"
echo "Valid intervals to process: ${VALIDATED_INTERVALS}"
if [ "$TEST_MODE" = true ]; then
    echo "MODE: TEST (short date range)"
else
    echo "MODE: PRODUCTION (full date range)"
fi
echo "Parallel processes: ${MAX_PARALLEL}"
echo "==========================================

"

# Process each symbol and interval
for symbol in ${SYMBOLS}; do
    echo "Processing symbol: ${symbol}"
    echo "--------------------"
    
    for interval in ${VALIDATED_INTERVALS}; do
        process_interval "${interval}" "${START_DATE}" "${END_DATE}" "${symbol}"
    done
    
    echo "Completed processing symbol: ${symbol}"
    echo ""
done

# Clean up the main temporary directory
fast_remove_dir "${TEMP_DIR}"

echo ""
echo "All symbol and interval verification completed."
echo ""
echo "REFERENCE INFORMATION:"
echo "--------------------"
echo "Market Types and Data Availability:"
echo "- SPOT: All intervals available (including 1s). Earliest dates vary by symbol."
echo "- UM (USDT-Margined Futures): All intervals except 1s. Earliest ~2019-12-31 for BTCUSDT."
echo "- CM (Coin-Margined Futures): All intervals except 1s. Uses symbols like BTCUSD_PERP." 
echo "  Earliest ~2020-09-23 for BCHUSD_PERP."
echo "" 