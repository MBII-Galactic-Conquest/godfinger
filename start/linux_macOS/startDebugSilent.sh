#!/bin/bash

# Navigate to the correct directory
cd ../../
cd ./update

# Check if python3, python2, or python is installed and use the correct one
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python2 &>/dev/null; then
    PYTHON_CMD="python2"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: No suitable Python installation found."
    exit 1
fi

# Get the version of the selected Python binary
PYTHON_VERSION=$($PYTHON_CMD --version)

echo "Using $PYTHON_CMD ($PYTHON_VERSION)"

# Run the update script using the correct Python version
$PYTHON_CMD ./update.py

# Go back to the previous directory and run cleanup
cd ../
./cleanup.sh

# Run godfinger script using the correct Python version with the --debug flag and the bigdata.log argument
$PYTHON_CMD ./godfinger.py --debug -lf "./bigdata.log"

# Wait for user input before exiting
read -p "Press Enter to continue..."
