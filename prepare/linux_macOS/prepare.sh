#!/bin/bash

# Navigate to the parent directory
cd ../ || { echo "Failed to navigate to parent directory."; exit 1; }

# Try to enter the bin directory, if it doesn't exist, show a message and exit
if ! cd ./bin; then
    echo "Bin folder with dependencies does not exist. Press enter to continue..."
    read -r input
    exit 1
fi

echo "Configuring virtual environment, please wait..."

# Check if virtual environment exists, create it if not
if ! test -f ../../venv/bin/activate; then
    python -m venv ../../venv
fi

# Activate the virtual environment (Linux style path)
source ../../venv/bin/activate || { echo "Failed to activate virtual environment"; exit 1; }
echo "Using Python at:"
which python

# Install dependencies
echo "Installing dependencies..."
python -m pip install -U -r requirements.txt || { echo "Error installing dependencies"; exit 1; }

# Run the prepare.py script
echo "Running ANSI-WIN1252 file-read-backwards patch..."
python ./prepare.py || { echo "Error running prepare.py"; exit 1; }

# Wait for user input before exiting
echo "Press enter to exit..."
read -r input
