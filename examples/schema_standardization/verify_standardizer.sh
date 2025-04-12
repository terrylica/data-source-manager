#!/bin/bash
# Script to verify the SchemaStandardizer functionality across different market types

# Navigate to project root
if [[ -d "core" && -d "utils" && -d "examples" ]]; then
  # Already in project root
  echo "Running from project root directory"
else
  # Try to navigate to project root
  if [[ -d "../../core" && -d "../../utils" ]]; then
    cd ../..
    echo "Changed to project root directory: $(pwd)"
  else
    echo "Error: Unable to locate project root directory"
    echo "Please run this script from either the project root or the examples/schema_standardization directory"
    exit 1
  fi
fi

# Set script to exit on error
set -e

# Define colors for output
GREEN='\033[1;32m'
BLUE='\033[1;34m'
CYAN='\033[1;36m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
NC='\033[0m' # No Color

# Define function to run the verification
run_standardizer_verification() {
  local market_type=$1
  local symbol=$2
  local interval=${3:-"1m"}
  local output_dir="./schema_test/${market_type}_${symbol}"
  
  echo -e "\n${CYAN}=================================================${NC}"
  echo -e "${CYAN}Running SchemaStandardizer Verification${NC}"
  echo -e "${CYAN}Market: $market_type | Symbol: $symbol | Interval: $interval${NC}"
  echo -e "${CYAN}=================================================${NC}"
  
  # Create output directory
  mkdir -p "$output_dir"
  
  # Build command with appropriate flags
  cmd="python examples/schema_standardization/verify_standardizer.py --market-type \"$market_type\" --symbol \"$symbol\" --interval \"$interval\" --output-dir \"$output_dir\""
  
  # Run the command
  eval $cmd
}

# Parse command line arguments
if [ $# -ge 1 ] && [ $# -le 3 ]; then
  # Run with user-specified parameters
  market_type=$1
  symbol=${2:-"BTCUSDT"}
  interval=${3:-"1m"}
  
  run_standardizer_verification "$market_type" "$symbol" "$interval"
  exit 0
fi

# Run verification for all market types
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}# SchemaStandardizer Verification #${NC}"
echo -e "${GREEN}=================================================${NC}"
echo -e "This will verify schema standardization across all data sources:"
echo -e "1. REST API (recent data)"
echo -e "2. Vision API (historical data)"
echo -e "3. Cache (stored data)"
echo -e ""
echo -e "Running verification for all market types..."

# SPOT market
run_standardizer_verification "SPOT" "BTCUSDT" "1m"

# UM futures market
run_standardizer_verification "UM" "BTCUSDT" "1m"

# CM futures market 
run_standardizer_verification "CM" "BTCUSD_PERP" "1m"

echo -e "\n${GREEN}Schema standardizer verification completed for all market types!${NC}"
echo -e "Check the ./schema_test directory for the raw and standardized data files."
exit 0 