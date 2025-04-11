#!/bin/bash
# Test script to demonstrate all features using small footprint test sizes

# Set script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BASE_DIR="$( cd "$SCRIPT_DIR/../.." && pwd )"

# Set colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Error log file
ERROR_LOG_FILE="${BASE_DIR}/logs/error_logs/test_run_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$ERROR_LOG_FILE")"

# Define test date range (use dates that are likely to have data, but not too recent)
# Use a smaller date range to speed up tests
START_DATE="2023-04-01"
END_DATE="2023-04-03"  # Just 3 days for quicker tests

# Define default market parameters - aligned with market_constraints.py
DATA_PROVIDER="BINANCE"
CHART_TYPE="KLINES"
MARKET_TYPE="spot"

# Function to print section header
print_header() {
    echo -e "\n${BLUE}==== $1 ====${NC}\n"
}

# Function to print info
print_info() {
    echo -e "${GREEN}$1${NC}"
}

# Function to print warning
print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

# Function to print error
print_error() {
    echo -e "${RED}$1${NC}"
}

# Display test date range
print_info "Using test date range: $START_DATE to $END_DATE"
print_info "Using market parameters: ${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}"

# Function to run test and wait for confirmation to continue
run_test() {
    print_header "$1"
    print_info "Running: $2"
    eval "$2"
    echo ""
    read -p "Press Enter to continue to next test..."
}

# Function to enable error logging via Python
enable_error_logging() {
    print_info "Setting up error logging to $ERROR_LOG_FILE"
    python -c "from utils.logger_setup import logger; logger.enable_error_logging('$ERROR_LOG_FILE'); print('Error logging configured successfully')"
}

# Function to display error log summary
display_error_log() {
    if [ -f "$ERROR_LOG_FILE" ]; then
        local count=$(wc -l < "$ERROR_LOG_FILE")
        if [ "$count" -gt 0 ]; then
            print_header "ERROR LOG SUMMARY"
            print_warning "Found $count log entries at WARNING level or higher:"
            print_info "Log file: $ERROR_LOG_FILE"
            
            # Show the first 10 lines of the error log
            print_info "First 10 entries:"
            head -n 10 "$ERROR_LOG_FILE"
            
            if [ "$count" -gt 10 ]; then
                print_info "... and $(($count - 10)) more entries. Check $ERROR_LOG_FILE for the complete log."
            fi
        else
            print_info "No errors or warnings were logged during the test run."
        fi
    else
        print_warning "Error log file not found: $ERROR_LOG_FILE"
    fi
}

# Function to check the cache directory
check_cache() {
    local SYMBOL="$1"
    local INTERVAL="$2"
    
    CACHE_DIR="${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}/${SYMBOL}/${INTERVAL}"
    print_info "Checking cache directory: ${CACHE_DIR}"
    
    if [ -d "$CACHE_DIR" ]; then
        print_info "Cache files:"
        ls -la "$CACHE_DIR"
    else
        print_warning "Cache directory does not exist yet"
    fi
    
    # Check the cache index database
    CACHE_DB="${BASE_DIR}/logs/cache_index.db"
    if [ -f "$CACHE_DB" ]; then
        echo -e "\n${GREEN}Cache index exists (SQLite database)${NC}"
        
        # Check if sqlite3 is available
        if command -v sqlite3 &> /dev/null; then
            print_info "Cache entries for ${SYMBOL}/${INTERVAL}:"
            sqlite3 "$CACHE_DB" "SELECT date, file_size, num_records, path FROM cache_entries WHERE symbol='${SYMBOL}' AND interval='${INTERVAL}' ORDER BY date;" 2>/dev/null || echo "Query failed or no entries found"
        else
            echo "Install sqlite3 for better cache index viewing"
        fi
    else
        print_warning "Cache index database does not exist yet"
    fi
}

# Function to run a complete test scenario
run_test_scenario() {
    local TEST_NAME="$1"
    local TEST_SIZE="$2"
    local BASE_CMD="$SCRIPT_DIR/cache_builder.sh -m test -t $TEST_SIZE --error-log $ERROR_LOG_FILE --start-date $START_DATE --end-date $END_DATE --market-type $MARKET_TYPE --data-provider $DATA_PROVIDER --chart-type $CHART_TYPE"
    local SYMBOL=$(echo "$3" | cut -d ',' -f1)  # Get first symbol from list
    local INTERVAL=$(echo "$4" | cut -d ',' -f1)  # Get first interval from list
    
    print_header "TEST SCENARIO: $TEST_NAME (size: $TEST_SIZE)"
    
    # Clear cache for this symbol and interval
    print_info "Clearing cache for test..."
    CACHE_DIR="${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}/${SYMBOL}/${INTERVAL}"
    rm -rf "$CACHE_DIR"
    print_info "Cache cleared for $SYMBOL/$INTERVAL"
    
    # Initial download
    print_info "Step 1: Initial download"
    $BASE_CMD
    
    # Run with the feature being tested
    print_info "Step 2: Testing $TEST_NAME feature"
    $BASE_CMD $5
    
    # Report results
    print_info "Results for $TEST_NAME:"
    ls -la "$CACHE_DIR" 2>/dev/null || echo "No cache directory found"
    
    echo ""
    read -p "Press Enter to continue to next scenario..."
    echo ""
}

# Function to run incremental test
run_incremental_test() {
    local SYMBOL="BTCUSDT"
    local INTERVAL="5m"
    
    print_header "INCREMENTAL TESTING SCENARIO"
    
    # Clear existing cache for this test
    print_header "Clearing existing cache"
    rm -rf "${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}/${SYMBOL}/${INTERVAL}"
    rm -f "${BASE_DIR}/logs/cache_index.db"
    print_info "Cache cleared"
    
    # Initial run - download all data
    print_header "Initial run - downloading all data"
    print_info "Running: ./cache_builder.sh --symbols ${SYMBOL} --intervals ${INTERVAL} --start-date ${START_DATE} --end-date ${END_DATE} --market-type ${MARKET_TYPE} --data-provider ${DATA_PROVIDER} --chart-type ${CHART_TYPE}"
    "$SCRIPT_DIR/cache_builder.sh" --symbols "$SYMBOL" --intervals "$INTERVAL" --start-date "$START_DATE" --end-date "$END_DATE" --market-type "$MARKET_TYPE" --data-provider "$DATA_PROVIDER" --chart-type "$CHART_TYPE"
    
    # Check cache after initial run
    print_header "Cache after initial run"
    check_cache "$SYMBOL" "$INTERVAL"
    
    # Run in incremental mode (should skip existing files)
    print_header "Running in incremental mode"
    print_info "Running: ./cache_builder.sh --symbols ${SYMBOL} --intervals ${INTERVAL} --start-date ${START_DATE} --end-date ${END_DATE} --incremental --market-type ${MARKET_TYPE} --data-provider ${DATA_PROVIDER} --chart-type ${CHART_TYPE}"
    "$SCRIPT_DIR/cache_builder.sh" --symbols "$SYMBOL" --intervals "$INTERVAL" --start-date "$START_DATE" --end-date "$END_DATE" --incremental --market-type "$MARKET_TYPE" --data-provider "$DATA_PROVIDER" --chart-type "$CHART_TYPE"
    
    # Force update (should re-download all files)
    print_header "Running with force update"
    print_info "Running: ./cache_builder.sh --symbols ${SYMBOL} --intervals ${INTERVAL} --start-date ${START_DATE} --end-date ${END_DATE} --force-update --market-type ${MARKET_TYPE} --data-provider ${DATA_PROVIDER} --chart-type ${CHART_TYPE}"
    "$SCRIPT_DIR/cache_builder.sh" --symbols "$SYMBOL" --intervals "$INTERVAL" --start-date "$START_DATE" --end-date "$END_DATE" --force-update --market-type "$MARKET_TYPE" --data-provider "$DATA_PROVIDER" --chart-type "$CHART_TYPE"
    
    # Delete some files to create gaps
    print_header "Creating gaps in the cache"
    rm -f "${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}/${SYMBOL}/${INTERVAL}/${START_DATE}.arrow"
    MIDDLE_DATE=$(date -d "$START_DATE + 1 day" +%Y-%m-%d)
    rm -f "${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}/${SYMBOL}/${INTERVAL}/${MIDDLE_DATE}.arrow"
    print_info "Deleted files for ${START_DATE} and ${MIDDLE_DATE} to create gaps"
    
    # Check cache with gaps
    print_header "Cache with gaps"
    check_cache "$SYMBOL" "$INTERVAL"
    
    # Fill gaps with gap detection
    print_header "Filling gaps with gap detection"
    print_info "Running: ./cache_builder.sh --symbols ${SYMBOL} --intervals ${INTERVAL} --start-date ${START_DATE} --end-date ${END_DATE} --detect-gaps --market-type ${MARKET_TYPE} --data-provider ${DATA_PROVIDER} --chart-type ${CHART_TYPE}"
    "$SCRIPT_DIR/cache_builder.sh" --symbols "$SYMBOL" --intervals "$INTERVAL" --start-date "$START_DATE" --end-date "$END_DATE" --detect-gaps --market-type "$MARKET_TYPE" --data-provider "$DATA_PROVIDER" --chart-type "$CHART_TYPE"
    
    # Check cache after filling gaps
    print_header "Cache after filling gaps"
    check_cache "$SYMBOL" "$INTERVAL"
    
    # Auto mode test with a new date range
    EXTENDED_END_DATE=$(date -d "$END_DATE + 3 day" +%Y-%m-%d)
    EXTENDED_START_DATE=$(date -d "$START_DATE - 1 day" +%Y-%m-%d)
    print_header "Testing auto mode with expanded date range"
    print_info "Note: Using -m test flag to prevent processing all symbols from CSV"
    print_info "Running: ./cache_builder.sh -m test -t very-small --symbols ${SYMBOL} --intervals ${INTERVAL} --start-date ${EXTENDED_START_DATE} --end-date ${EXTENDED_END_DATE} --detect-gaps --incremental --market-type ${MARKET_TYPE} --data-provider ${DATA_PROVIDER} --chart-type ${CHART_TYPE}"
    "$SCRIPT_DIR/cache_builder.sh" -m test -t very-small --symbols "$SYMBOL" --intervals "$INTERVAL" --start-date "$EXTENDED_START_DATE" --end-date "$EXTENDED_END_DATE" --detect-gaps --incremental --market-type "$MARKET_TYPE" --data-provider "$DATA_PROVIDER" --chart-type "$CHART_TYPE"
    
    # Final cache check
    print_header "Final cache state"
    check_cache "$SYMBOL" "$INTERVAL"
    
    print_header "Incremental test complete"
    print_info "The test demonstrated:"
    print_info "1. Initial data download"
    print_info "2. Incremental updates (skipping existing files)"
    print_info "3. Force updates (re-downloading files)"
    print_info "4. Gap detection and filling"
    print_info "5. Auto mode for extended date ranges"
    print_info "6. Proper use of market parameters: ${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}"
    
    read -p "Press Enter to continue with other tests..."
}

# Function to clean up and validate cache index files
clean_cache_index_files() {
    print_header "CLEANING CACHE INDEX FILES"
    
    # Check for existing SQLite database
    CACHE_DB="${BASE_DIR}/logs/cache_index.db"
    CACHE_INDEX="${BASE_DIR}/logs/cache_index.json"
    BACKUP_DIR="${BASE_DIR}/logs/cache_index_backups"
    mkdir -p "$BACKUP_DIR"
    
    # Check if sqlite3 is available
    if command -v sqlite3 >/dev/null 2>&1; then
        print_info "SQLite3 is available"
        
        # If the SQLite database exists, validate it
        if [ -f "$CACHE_DB" ]; then
            print_info "Found existing cache SQLite database"
            
            # Check file size - if empty or very small, just recreate it
            if [ ! -s "$CACHE_DB" ] || [ $(stat -c%s "$CACHE_DB") -lt 1000 ]; then
                print_warning "Cache database file is empty or very small, will be recreated"
                rm -f "$CACHE_DB"
            else
                # Verify database integrity
                if sqlite3 "$CACHE_DB" "PRAGMA integrity_check;" 2>/dev/null | grep -q "ok"; then
                    print_info "Cache database integrity check passed"
                    
                    # Display database structure
                    print_info "Database tables:"
                    sqlite3 "$CACHE_DB" ".tables"
                    
                    # Display sample entries
                    print_info "Sample entries from cache_entries table:"
                    sqlite3 "$CACHE_DB" "SELECT symbol, interval, date, file_size, num_records FROM cache_entries LIMIT 5;"
                else
                    print_warning "Cache database failed integrity check, creating backup"
                    BACKUP_FILE="${BACKUP_DIR}/cache_index_$(date +%Y%m%d_%H%M%S).db.bak"
                    cp "$CACHE_DB" "$BACKUP_FILE"
                    print_info "Backed up to: $BACKUP_FILE"
                    
                    # Remove the corrupted database
                    rm -f "$CACHE_DB"
                    print_info "Removed corrupted cache database"
                fi
            fi
        else
            print_info "No existing SQLite database found, will be created during tests"
        fi
    else
        print_warning "SQLite3 command not available, cannot validate database"
    fi
    
    # Check for existing JSON index file (legacy)
    if [ -f "$CACHE_INDEX" ]; then
        print_warning "Found legacy JSON cache index file - this format is deprecated"
        print_info "The new SQLite database format will be used instead"
        
        # Create a backup of the legacy file
        BACKUP_FILE="${BACKUP_DIR}/legacy_cache_index_$(date +%Y%m%d_%H%M%S).json.bak"
        cp "$CACHE_INDEX" "$BACKUP_FILE"
        print_info "Backed up legacy file to: $BACKUP_FILE"
        
        # Optionally remove the old file to avoid confusion
        read -p "Remove legacy JSON file? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -f "$CACHE_INDEX"
            print_info "Removed legacy JSON cache index file"
        else
            print_info "Kept legacy JSON file for reference"
        fi
    else
        print_info "No legacy JSON cache index found (good)"
    fi
    
    # Check for checksum failures registry
    CHECKSUM_REGISTRY="${BASE_DIR}/logs/checksum_failures/registry.json"
    if [ -f "$CHECKSUM_REGISTRY" ]; then
        print_info "Found existing checksum failures registry"
        
        # Check file size - if empty, just recreate it
        if [ ! -s "$CHECKSUM_REGISTRY" ]; then
            print_warning "Checksum failures registry is empty, creating new file"
            echo '[]' > "$CHECKSUM_REGISTRY"
            print_info "Created new valid checksum failures registry"
            return
        fi
        
        # Check if jq is available for better JSON handling
        if command -v jq >/dev/null 2>&1; then
            print_info "Using jq for JSON validation and normalization"
            
            # Try to normalize the JSON using jq
            TEMP_JSON="${BACKUP_DIR}/temp_normalized_$(date +%Y%m%d_%H%M%S).json"
            if jq '.' "$CHECKSUM_REGISTRY" > "$TEMP_JSON" 2>/dev/null; then
                print_info "Successfully normalized JSON with jq"
                
                # Create a backup before replacing
                BACKUP_FILE="${BACKUP_DIR}/registry_$(date +%Y%m%d_%H%M%S).json.bak"
                cp "$CHECKSUM_REGISTRY" "$BACKUP_FILE"
                print_info "Backed up to: $BACKUP_FILE"
                
                # Replace with normalized version
                cp "$TEMP_JSON" "$CHECKSUM_REGISTRY"
                print_info "Replaced with normalized JSON"
                rm -f "$TEMP_JSON"
            else
                print_warning "jq could not parse the JSON file, creating new file"
                BACKUP_FILE="${BACKUP_DIR}/registry_$(date +%Y%m%d_%H%M%S).json.bak"
                cp "$CHECKSUM_REGISTRY" "$BACKUP_FILE" 
                print_info "Backed up to: $BACKUP_FILE"
                
                # Create a new empty valid JSON file
                echo '[]' > "$CHECKSUM_REGISTRY"
                print_info "Created new valid checksum failures registry"
            fi
        else
            # Verify if it's valid JSON using Python
            if python -c "import json; json.load(open('$CHECKSUM_REGISTRY'))" 2>/dev/null; then
                print_info "Checksum failures registry is valid JSON"
            else
                print_warning "Checksum failures registry contains invalid JSON, creating backup"
                BACKUP_FILE="${BACKUP_DIR}/registry_$(date +%Y%m%d_%H%M%S).json.bak"
                cp "$CHECKSUM_REGISTRY" "$BACKUP_FILE"
                print_info "Backed up to: $BACKUP_FILE"
                
                # Remove the corrupted file
                rm -f "$CHECKSUM_REGISTRY"
                print_info "Removed corrupted checksum failures registry"
                
                # Create a new empty valid JSON file
                echo '[]' > "$CHECKSUM_REGISTRY"
                print_info "Created new valid checksum failures registry"
            fi
        fi
    else
        print_info "No existing checksum failures registry found, will be created during tests"
    fi
}

# Set up error logging before starting tests
enable_error_logging

# Clear all the test data before starting
print_header "PREPARING TEST ENVIRONMENT"
print_info "Clearing all cache data..."
rm -rf "${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}"
rm -f "${BASE_DIR}/logs/cache_index.db"
rm -f "${BASE_DIR}/logs/cache_index.json"  # Remove legacy file if it exists
rm -f "${BASE_DIR}/logs/checksum_failures/registry.json"
print_info "Cache cleared"

# Display options for tests to run
print_header "AVAILABLE TESTS"
print_info "1. Run Incremental Testing Suite"
print_info "2. Run Basic Cache Building Test"
print_info "3. Run Incremental Update Test"
print_info "4. Run Force Update Test"
print_info "5. Run Gap Detection Test"
print_info "6. Run Auto Mode Test"
print_info "7. Run Combined Features Test"
print_info "8. Run Gap Detection Detailed Test"
print_info "9. Run Checksum Handling Test"
print_info "10. Run All Tests"
print_info "11. Clean Cache Index Files"
print_info "0. Exit"

# Get user input
read -p "Enter test number(s) to run (space-separated, e.g., '1 3 5'): " -a TEST_CHOICES

# Process user input
if [[ " ${TEST_CHOICES[@]} " =~ " 0 " ]]; then
    print_info "Exiting without running tests"
    exit 0
fi

if [[ " ${TEST_CHOICES[@]} " =~ " 10 " ]]; then
    # Run all tests
    TEST_CHOICES=(1 2 3 4 5 6 7 8 9 11)
fi

for choice in "${TEST_CHOICES[@]}"; do
    case $choice in
        1)
            # Run Incremental Testing Suite (from test_incremental.sh)
            run_incremental_test
            ;;
        2)
            # Test 1: Very Small Footprint Basic Test
            run_test_scenario "Basic Cache Building" "very-small" "BTCUSDT" "5m" ""
            ;;
        3)
            # Test 2: Incremental Update (Very Small)
            run_test_scenario "Incremental Update" "very-small" "BTCUSDT" "5m" "--incremental"
            ;;
        4)
            # Test 3: Force Update (Very Small)
            run_test_scenario "Force Update" "very-small" "BTCUSDT" "5m" "--force-update"
            ;;
        5)
            # Test 4: Gap Detection (Small Size)
            run_test_scenario "Gap Detection" "small" "BTCUSDT,ETHUSDT,BNBUSDT" "5m" "--detect-gaps"
            ;;
        6)
            # Test 5: Auto Mode (Small Size)
            run_test_scenario "Auto Mode" "small" "BTCUSDT,ETHUSDT,BNBUSDT" "5m" "--auto"
            ;;
        7)
            # Test 6: Combined Features Test (Medium Size)
            run_test_scenario "Combined Features" "medium" "BTCUSDT,ETHUSDT,BNBUSDT,XRPUSDT,ADAUSDT" "5m,1h" "--incremental --detect-gaps"
            ;;
        8)
            # Create gap test (manually delete files and then detect gaps)
            print_header "GAP DETECTION DETAILED TEST"
            print_info "Step 1: Initial download (medium size)"
            $SCRIPT_DIR/cache_builder.sh -m test -t medium --error-log $ERROR_LOG_FILE --start-date $START_DATE --end-date $END_DATE --market-type $MARKET_TYPE --data-provider $DATA_PROVIDER --chart-type $CHART_TYPE

            print_info "Step 2: Creating gaps by deleting some files..."
            SYMBOL="BTCUSDT"
            INTERVAL="5m"
            CACHE_DIR="${BASE_DIR}/cache/${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}/${SYMBOL}/${INTERVAL}"
            FILES=$(ls "$CACHE_DIR" | sort)
            COUNT=$(echo "$FILES" | wc -l)

            # Delete every other file to create gaps
            i=0
            for file in $FILES; do
                if [ $((i % 2)) -eq 0 ]; then
                    rm -f "${CACHE_DIR}/${file}"
                    print_info "Deleted ${CACHE_DIR}/${file}"
                fi
                i=$((i+1))
            done

            print_info "Step 3: Running gap detection to fill missing files"
            $SCRIPT_DIR/cache_builder.sh -m test -t medium --detect-gaps --error-log $ERROR_LOG_FILE --start-date $START_DATE --end-date $END_DATE --market-type $MARKET_TYPE --data-provider $DATA_PROVIDER --chart-type $CHART_TYPE

            print_info "Final result after gap filling:"
            ls -la "$CACHE_DIR"
            
            read -p "Press Enter to continue with other tests..."
            ;;
        9)
            # Test checksum features
            print_header "CHECKSUM HANDLING TEST"
            print_info "Step 1: Run with proceed-on-failure flag"
            $SCRIPT_DIR/cache_builder.sh -m test -t very-small --proceed-on-failure --error-log $ERROR_LOG_FILE --start-date $START_DATE --end-date $END_DATE --market-type $MARKET_TYPE --data-provider $DATA_PROVIDER --chart-type $CHART_TYPE

            print_info "Step 2: Check checksum failures registry"
            if [ -f "${BASE_DIR}/logs/checksum_failures/registry.json" ]; then
                print_info "Checksum failures registry exists:"
                cat "${BASE_DIR}/logs/checksum_failures/registry.json" | head -20
            else
                print_info "No checksum failures detected"
            fi

            print_info "Step 3: Run retry-failed-checksums if any failures exist"
            if [ -f "${BASE_DIR}/logs/checksum_failures/registry.json" ] && [ -s "${BASE_DIR}/logs/checksum_failures/registry.json" ]; then
                $SCRIPT_DIR/cache_builder.sh -m test -t very-small --retry-failed-checksums --error-log $ERROR_LOG_FILE --start-date $START_DATE --end-date $END_DATE --market-type $MARKET_TYPE --data-provider $DATA_PROVIDER --chart-type $CHART_TYPE
            else
                print_info "Skipping retry as no failures were detected"
            fi
            
            read -p "Press Enter to continue with other tests..."
            ;;
        11)
            # Clean Cache Index Files
            clean_cache_index_files
            ;;
        *)
            print_warning "Invalid test number: $choice"
            ;;
    esac
done

print_header "ALL TESTS COMPLETE"
print_info "The tests demonstrated:"
print_info "1. Basic cache building with various footprint sizes"
print_info "2. Incremental updates (skipping existing files)"
print_info "3. Force updates (re-downloading files)"
print_info "4. Gap detection and filling"
print_info "5. Auto mode functionality"
print_info "6. Combined features test"
print_info "7. Checksum handling"
print_info "8. Proper use of market parameters: ${DATA_PROVIDER}/${CHART_TYPE}/${MARKET_TYPE}"

# Display the error log summary
display_error_log

print_header "TEST RUN FINISHED"
print_info "Error log file: $ERROR_LOG_FILE"