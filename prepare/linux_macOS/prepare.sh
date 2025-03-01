#!/bin/bash

# Navigate up one level
cd ../

# Try to enter the bin directory, if it doesn't exist, show a message and wait for user input
if ! cd ./bin; then
    echo "Bin folder with dependencies does not exist. Press enter to continue..."
    read -r input
else
    # Check if python3 is installed, otherwise fallback to python
    if command -v python3 &>/dev/null; then
        PYTHON_CMD="python3"
        PIP_CMD="pip3"
    elif command -v python2 &>/dev/null; then
        PYTHON_CMD="python2"
        PIP_CMD="pip2"
    elif command -v python &>/dev/null; then
        PYTHON_CMD="python"
        PIP_CMD="pip"
    else
        echo "Error: Python is not installed."
        exit 1
    fi

    # Install dependencies
    echo "Installing dependencies..."
    $PIP_CMD install -U -r requirements.txt --break-system-packages
fi

# Wait for user input before exiting
echo "Press enter to exit..."
read -r input
