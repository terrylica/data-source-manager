#!/bin/bash

# Recursively find and remove empty directories
# The '-depth' option makes find traverse the directories in a depth-first way,
# so that it will find and remove the most deeply nested empty directories first.

# Run this multiple times to remove directories that become empty after their subdirectories are removed
for i in {1..5}; do
  echo "Pass $i:"
  find . -type d -not -path "*.git*" -not -path "*.venv*" -empty -print -delete
done

echo "Empty directory removal complete" 