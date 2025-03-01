#!/bin/bash

# Initialize a flag to track if __pycache__ directories are found
found=0

# Search for any __pycache__ directories
while IFS= read -r -d '' dir; do
    found=1
done < <(find . -type d -name "__pycache__" -print0)

# If no __pycache__ folders were found, print the message and exit
if [ "$found" -eq 0 ]; then
    echo "No __pycache__ folders detected for cleanup."
    read -p "Press enter to exit"
    exit 0
fi

# If __pycache__ folders are found, proceed with deletion
echo "Deleting __pycache__ folders..."
find . -type d -name "__pycache__" -exec rm -rf {} +

echo "__pycache__ folders should be regularly emptied after each session."
echo "Pycache cleanup complete."

# Pause before exiting
read -p "Press enter to continue..."
