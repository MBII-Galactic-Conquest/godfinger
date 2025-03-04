#!/bin/bash

# Prompt the user for confirmation
read -p "Do you wish to do __pycache__ cleanup? This can prevent conflicts. (Y/N): " choice

# Convert input to lowercase
choice=$(echo "$choice" | tr '[:upper:]' '[:lower:]')

if [[ "$choice" != "y" ]]; then
    echo "Pycache cleanup aborted."
    exit 0
fi

# Find and delete __pycache__ directories
found=0
while IFS= read -r -d '' dir; do
    found=1
    echo "Deleting: $dir"
    rm -rf "$dir"
done < <(find . -type d -name "__pycache__" -print0)

# If no __pycache__ folders were found
if [[ $found -eq 0 ]]; then
    echo "No __pycache__ folders detected for cleanup."
else
    echo "Pycache cleanup complete."
    echo "__pycache__ folders should be regularly emptied after each session."
fi

# Wait for user input before exiting
read -p "Press enter to continue..."
