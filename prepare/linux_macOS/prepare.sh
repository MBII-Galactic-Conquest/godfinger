#!/bin/bash

# Navigate up one level
cd ../

# Try to enter the bin directory, if it doesn't exist, show a message and wait for user input
if ! cd ./bin; then
    echo "Bin folder with dependencies does not exist. Press enter to continue..."
    read -r input
    exit 1
fi

echo Configuring virtual environment, please wait...

# Check if virtual environment exists, create it if not
if ! test -f ../../venv/bin/activate; then
    python -m venv ../../venv
fi
source ../../venv/bin/activate
echo Using python at
which python

# Function to check if Python meets the required version
check_python_version() {
    REQUIRED_VERSION="3.12.0"
    INSTALLED_VERSION=$($1 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")

    if [ -z "$INSTALLED_VERSION" ]; then
        echo "Error: Unable to check Python version with $1 (possibly missing or permission denied)"
        return 1
    fi

    echo "Installed Python version: $INSTALLED_VERSION"
    echo "Required Python version: $REQUIRED_VERSION"

    # Compare versions directly (e.g., 3.12.1 > 3.12.0)
    INSTALLED_VERSION_NUM=$(echo "$INSTALLED_VERSION" | tr -d '.')
    REQUIRED_VERSION_NUM=$(echo "$REQUIRED_VERSION" | tr -d '.')

    if [ "$INSTALLED_VERSION_NUM" -ge "$REQUIRED_VERSION_NUM" ]; then
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

# Check for latest pip
echo "Checking for latest pip package..."
$PIP_CMD install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
$PIP_CMD install -U -r requirements.txt --break-system-packages

# Wait for user input before exiting
echo "Press enter to exit..."
read -r input
