#!/bin/bash

# clear_logs.sh
# This script deletes all log files starting with "bigdata.log" in the current directory.
# This includes 'bigdata.log' and all timestamped backups like 'bigdata.log-10022025_143'.

echo "Checking for log files to delete..."

# Check if any files matching the pattern exist before attempting deletion.
# The 'ls bigdata.log*' correctly uses the wildcard to find all matching files.
if ls bigdata.log* 1> /dev/null 2>&1; then
    
    # Use 'rm' to remove files matching the pattern silently (-f).
    rm -f bigdata.log*

    # Check the exit status of the previous command (rm)
    if [ $? -eq 0 ]; then
        echo ""
        echo "Successfully deleted all files matching 'bigdata.log*'."
        echo ""
    else
        echo ""
        echo "ERROR: An issue occurred during deletion. Some files may be in use or protected."
        echo ""
    fi

else
    echo "No files matching 'bigdata.log*' found in the current directory."
fi
