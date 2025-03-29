#!/bin/bash

# Function to install SVN based on OS
install_svn() {
    echo "Checking system for package manager..."

    if [[ "$(uname)" == "Darwin" ]]; then
        # macOS (using Homebrew)
        if command -v brew &>/dev/null; then
            echo "Installing SVN on macOS using Homebrew..."
            brew install subversion
        else
            echo "Homebrew not found. Please install Homebrew first: https://brew.sh/"
            exit 1
        fi
    elif [[ -x "$(command -v apt-get)" ]]; then
        # Debian/Ubuntu-based Linux
        echo "Installing SVN on Debian/Ubuntu-based system..."
        sudo apt-get update && sudo apt-get install -y subversion
    elif [[ -x "$(command -v yum)" ]]; then
        # RedHat/CentOS-based Linux
        echo "Installing SVN on RedHat/CentOS-based system..."
        sudo yum install -y subversion
    else
        echo "Unsupported OS or package manager. Please install SVN manually."
        exit 1
    fi
}

# Run the install function
install_svn

# Verify if SVN is installed and available in the PATH
if command -v svn &>/dev/null; then
    echo "SVN successfully installed. Version: $(svn --version | head -n 1)"
else
    echo "SVN installation failed. Please check your system configuration."
    exit 1
fi
