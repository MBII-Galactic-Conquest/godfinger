#!/bin/bash

# Function to check if jq is installed
check_jq() {
    if ! command -v jq &> /dev/null; then
        echo "jq is not installed. Installing jq..."
        
        # Install jq depending on the package manager
        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS (using Homebrew)
            brew install jq
        elif [[ -x "$(command -v apt-get)" ]]; then
            # Debian/Ubuntu-based Linux
            sudo apt-get update && sudo apt-get install -y jq
        elif [[ -x "$(command -v yum)" ]]; then
            # RedHat/CentOS-based Linux
            sudo yum install -y jq
        else
            echo "Unsupported OS or package manager. Please install jq manually."
            exit 1
        fi
    else
        echo "jq is already installed."
    fi
}

# SVN Repository and Working Copy Paths
REPO_PATH=$1
REVISION=$2
WORKING_COPY="./"
CONFIG_FILE="svnConfig.json"

# Check if svnConfig.json exists, if not create it with default values
if [[ ! -f "$CONFIG_FILE" ]]; then
    cat <<EOF > "$CONFIG_FILE"
{
    "username": "",
    "password": "",
    "accept_choice": "theirs-full"
}
EOF
    echo "svnConfig.json created with empty username, password, and default accept_choice."
fi

# Check if jq is installed, if not install it
check_jq

# Read username, password, and accept_choice from svnConfig.json
USERNAME=$(jq -r '.username' "$CONFIG_FILE")
PASSWORD=$(jq -r '.password' "$CONFIG_FILE")
ACCEPT_CHOICE=$(jq -r '.accept_choice' "$CONFIG_FILE")

# Log the commit information
echo "Commit to $REPO_PATH at revision $REVISION" >> "./svn_commits.log"

# Update the working copy
svn update "$WORKING_COPY" --username "$USERNAME" --password "$PASSWORD" --non-interactive --accept "$ACCEPT_CHOICE"

read -p "Press enter to exit..." input
