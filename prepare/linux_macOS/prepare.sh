#!/bin/bash

# Navigate up one level
cd ../

# Try to enter the bin directory, if it doesn't exist, show a message and wait for user input
if ! cd ./bin; then
    echo "Bin folder with dependencies does not exist. Press enter to continue..."
    read -r input
    exit 1
fi


if ! test -f ../../venv/Scripts/activate; then
    python -m venv ../../venv
fi
source ../../venv/Scripts/activate
echo Using python at
which python

# Function to check if Python meets the required version
check_python_version() {
    REQUIRED_VERSION="3.12.0"
    INSTALLED_VERSION=$($1 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")

    # Use sort to compare versions
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$INSTALLED_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
        echo "Using $1 (Python $INSTALLED_VERSION)"
        return 0
    else
        echo "Python version too old: $INSTALLED_VERSION (requires $REQUIRED_VERSION or newer)"
        return 1
    fi
}

# Determine the appropriate Python command (must be Python 3.12+)
if command -v python3 &>/dev/null && check_python_version "python3"; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
elif command -v python &>/dev/null && check_python_version "python"; then
    PYTHON_CMD="python"
    PIP_CMD="pip"
else
    echo "Error: Python 3.12+ is required but not found."
    echo "Please install Python 3.12 or newer and try again."
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
$PIP_CMD install -U -r requirements.txt --break-system-packages

# Wait for user input before exiting
echo "Press enter to exit..."
read -r input
