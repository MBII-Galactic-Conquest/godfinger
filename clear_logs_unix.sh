#!/bin/bash

# clear_logs.sh
# This script deletes all log files starting with "bigdata.log" in the current and all recursive subdirectories.
# This includes 'bigdata.log' and all timestamped backups like 'bigdata.log-10022025_143'.

echo "Checking for log files to delete..."

found_files=$(find . -type f -name "bigdata.log*")

# Check if any files matching the pattern exist before attempting deletion.
# The 'ls bigdata.log*' correctly uses the wildcard to find all matching files.
if [ -n "$found_files" ]; then
    echo "Deleting the following files:"
    echo "$found_files"
    echo ""

    # Delete all found files quietly (-f)
    find . -type f -name "bigdata.log*" -exec rm -f {} +

    # Check if deletion was successful
    if [ $? -eq 0 ]; then
        echo "Successfully deleted all files matching 'bigdata.log*'."
    else
        echo "ERROR: An issue occurred during deletion. Some files may be in use or protected."
    fi
else
    echo "No files matching 'bigdata.log*' found in the current directory or subdirectories."
fi
