#!/bin/bash
set -e

# Navigate up one level
cd ../

# Try to enter the bin directory, if it doesn't exist, show a message and wait for user input
if ! cd ./bin; then
    echo "Error: Bin folder with dependencies does not exist." >&2
    echo "Please create the bin directory and try again."
    read -r input
    exit 1
fi

echo "Configuring virtual environment, please wait..."

# Check if virtual environment exists, create it if not
VENV_DIR="../../venv"
if ! test -f "$VENV_DIR/bin/activate"; then
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
echo "Using python at"
which python

# Function to check if Python meets the required version
check_python_version() {
    REQUIRED_VERSION="3.12.0"
    INSTALLED_VERSION=$($1 -c "import sys; print('.'.join(map(str, sys.version_info[:3])))")

    if [ -z "$INSTALLED_VERSION" ]; then
        echo "Error: Unable to check Python version with $1 (possibly missing or permission denied)" >&2
        return 1
    fi

    echo "Installed Python version: $INSTALLED_VERSION"
    echo "Required Python version: $REQUIRED_VERSION"

    if printf '%s\n' "$REQUIRED_VERSION" "$INSTALLED_VERSION" | sort -V | head -n1 | grep -q "$REQUIRED_VERSION"; then
        echo "Using $1 (Python $INSTALLED_VERSION)"
        return 0
    else
        echo "Python version too old: $INSTALLED_VERSION (requires $REQUIRED_VERSION or newer)" >&2
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
    echo "Error: Python 3.12+ is required but not found." >&2
    echo "Please install Python 3.12 or newer and try again."
    exit 1
fi

# Check for latest pip
echo "Checking for latest pip package..."
$PIP_CMD install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
$PIP_CMD install -U -r requirements.txt

# Wait for user input before exiting
echo "Press enter to exit..."
read -r input
