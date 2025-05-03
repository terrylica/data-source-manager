#!/bin/bash

# Script to add executable permissions to Python and shell scripts
# To be run during devcontainer setup

echo "Adding executable permissions to Python and shell scripts..."

# Find and make all Python files executable
find /workspaces/raw-data-services -type f -name "*.py" -exec chmod +x {} \;

# Find and make all shell scripts executable
find /workspaces/raw-data-services -type f -name "*.sh" -exec chmod +x {} \;

# Also make any files with a shebang line executable
find /workspaces/raw-data-services -type f -exec grep -l "^#!" {} \; | xargs -r chmod +x

echo "Done! All Python and shell scripts now have executable permissions." 