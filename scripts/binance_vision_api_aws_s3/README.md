# Binance Vision API & AWS S3 Data Downloader

This directory contains scripts for downloading and verifying data from the Binance Vision API and AWS S3 storage.

## Enhancements to verify_multi_interval.sh

The `verify_multi_interval.sh` script has been enhanced to improve handling of download errors and to provide better diagnostics. Key improvements include:

1. **Improved file existence checking**

   - Checks if files exist before attempting downloads
   - Returns specific error codes for 404 (not found) vs. other types of errors
   - Reduces unnecessary retries for files that don't exist

2. **Better error categorization**

   - Clearly identifies and categorizes different failure types:
     - Files not found (404) - likely due to no data for that date
     - Download failures - network or server issues
     - Checksum errors - data corruption or transmission issues
     - Unzip failures - potentially corrupted archives

3. **Enhanced debugging information**

   - Shows HTTP status codes for download requests
   - Provides clearer progress indicators
   - Displays debugging information when issues occur

4. **Statistics and summary reporting**

   - Tracks total files processed, downloaded, not found, etc.
   - Generates summary reports with statistics
   - Provides recommendations based on error patterns

5. **Smarter retry logic**
   - Only retries downloads for issues that could be resolved by retrying
   - Avoids unnecessary retries for files that don't exist
   - Uses exponential backoff to reduce server load

## Usage

```bash
# Run the script with default settings
./verify_multi_interval.sh

# Edit the configuration section at the top of the script to customize:
# - Market type (spot, um, cm)
# - Symbols to download
# - Time intervals
# - Date ranges
# - Parallel processing settings
```

## Troubleshooting Common Issues

### "File not found" errors

These are expected for dates before a symbol started trading or for dates when trading was suspended. They are not script errors.

### Download failures

If you encounter download failures:

1. Check your network connection
2. Reduce MAX_PARALLEL (try 10-20)
3. Increase DOWNLOAD_TIMEOUT (try 60-120 seconds)
4. Run again with a more focused symbol/interval list

### For LUNA/UST specific issues

During May 2022, the LUNA/UST collapse occurred, which may have resulted in trading suspensions and missing data files for certain dates.
