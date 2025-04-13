#!/bin/bash
# Demo script to run the vision_only.py example
# This demonstrates fetching BTCUSDT data for multiple intervals (1s, 1m, 3m, 5m, 15m, 1h)
# directly from the Binance Vision API and compares timestamp formats
# to detect the timestamp misalignment issue documented in docs

# ANSI color codes
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Print header
echo -e "${CYAN}=======================================${NC}"
echo -e "${CYAN} Multi-Interval Timestamp Analysis${NC}"
echo -e "${CYAN}=======================================${NC}"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed or not in PATH${NC}"
    exit 1
fi

# Ensure required dependencies for direct data download
echo -e "${YELLOW}Checking for required Python packages...${NC}"
python3 -c "import httpx" 2>/dev/null
if [ $? -ne 0 ]; then
    echo -e "${YELLOW}Installing httpx package for HTTP requests...${NC}"
    pip install httpx
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to install httpx package${NC}"
        echo -e "${RED}Please run: pip install httpx${NC}"
        exit 1
    fi
fi

# Check if output directory exists and create if needed
OUTPUT_DIR="./examples/dsm_sync_focus/output"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/raw"

# Check if the script exists
SCRIPT_PATH="vision_only.py"
if [ ! -f "$SCRIPT_PATH" ]; then
    echo -e "${YELLOW}Looking for script in parent directory...${NC}"
    SCRIPT_PATH="../dsm_sync_focus/vision_only.py"
    if [ ! -f "$SCRIPT_PATH" ]; then
        echo -e "${RED}Error: Could not find vision_only.py script${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}Starting multi-interval timestamp analysis demo...${NC}"
echo -e "${MAGENTA}This will:${NC}"
echo -e "${MAGENTA}1. Fetch data for multiple intervals: 1s, 1m, 3m, 5m, 15m, 1h${NC}"
echo -e "${MAGENTA}2. Compare March 15, 2023 (millisecond format) and March 15, 2025 (microsecond format)${NC}"
echo -e "${MAGENTA}3. Detect timestamp misalignment issues across all interval types${NC}"
echo -e "${YELLOW}Timestamp: $(date)${NC}"
echo ""

# Run the Python script
python3 "$SCRIPT_PATH"
RESULT=$?

echo ""
if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}Demo completed successfully!${NC}"
    echo -e "${CYAN}Check the results:${NC}"
    echo -e "${CYAN}1. CSV files: ${OUTPUT_DIR}/BTCUSDT_*_vision_data_*.csv${NC}"
    echo -e "${CYAN}2. Raw data: ${OUTPUT_DIR}/raw/BTCUSDT-*-*-raw.csv${NC}"
    echo -e "${CYAN}3. Per-interval analysis: ${OUTPUT_DIR}/timestamp_analysis_report.json${NC}"
    echo -e "${CYAN}4. Multi-interval summary: ${OUTPUT_DIR}/multi_interval_analysis.json${NC}"
    echo -e "${CYAN}5. Logs: ./logs/vision_client_debug_*.log${NC}"
else
    echo -e "${RED}Demo failed with exit code: $RESULT${NC}"
    echo -e "${YELLOW}Please check the logs for more information${NC}"
fi

echo ""
echo -e "${CYAN}=======================================${NC}"
echo -e "${CYAN}    Multi-Interval Analysis Complete${NC}"
echo -e "${CYAN}=======================================${NC}"

# Open the analysis report if available
if [ -f "${OUTPUT_DIR}/multi_interval_analysis.json" ]; then
    echo -e "${GREEN}Would you like to view the multi-interval analysis summary? (y/n)${NC}"
    read -r VIEW_REPORT
    if [[ "$VIEW_REPORT" =~ ^[Yy]$ ]]; then
        if command -v jq &> /dev/null; then
            echo -e "${YELLOW}Displaying intervals with misalignment:${NC}"
            for interval in 1s 1m 3m 5m 15m 1h; do
                if jq -e ".\"$interval\".has_misalignment" "${OUTPUT_DIR}/multi_interval_analysis.json" > /dev/null; then
                    echo -e "${RED}$interval: Misaligned${NC}"
                else
                    echo -e "${GREEN}$interval: Aligned${NC}"
                fi
            done
        else
            less "${OUTPUT_DIR}/multi_interval_analysis.json" | cat
        fi
    fi
fi

exit $RESULT 