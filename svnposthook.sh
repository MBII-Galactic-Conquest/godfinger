#!/bin/bash

###############################################
# ENSURE SVN IS INSTALLED ON YOUR SYSTEM PATH #
###############################################

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
WORKING_COPY="./"
CONFIG_FILE="svnConfig.json"
LOG_FILE="./svn_update_log.log"

# Create a log file to capture all output for debugging
echo "svnposthook.sh started at $(date)\n" > "$LOG_FILE"

# Check if svnConfig.json exists, if not create it with default values
if [[ ! -f "$CONFIG_FILE" ]]; then
    cat <<EOF > "$CONFIG_FILE"
{
    "repo_path": "",
    "revision": "",
    "username": "",
    "password": "",
    "accept_choice": "theirs-full"
}
EOF
    echo "svnConfig.json created with empty username, password, and default accept_choice.\n" >> "$LOG_FILE"
fi

# Check if jq is installed, if not install it
check_jq

# Read username, password, and accept_choice from svnConfig.json
REPO_PATH=$(jq -r '.repo_path' "$CONFIG_FILE")
REVISION=$(jq -r '.revision' "$CONFIG_FILE")
USERNAME=$(jq -r '.username' "$CONFIG_FILE")
PASSWORD=$(jq -r '.password' "$CONFIG_FILE")
ACCEPT_CHOICE=$(jq -r '.accept_choice' "$CONFIG_FILE")

# Check if .svn folder exists in the current directory
if [[ ! -d "$WORKING_COPY/.svn" ]]; then
    echo "The working copy is not checked out. Checking out repository $REPO_PATH at revision $REVISION...\n" >> "$LOG_FILE"
    
    # Checkout the repository from $REPO_PATH at $REVISION
    svn checkout --username "$USERNAME" --password "$PASSWORD" --non-interactive --verbose "$REVISION" "$REPO_PATH" "$WORKING_COPY" >> "$LOG_FILE" 2>&1
    
    if [[ $? -ne 0 ]]; then
        echo "Checkout failed. Please check the repository URL, revision, or your credentials.\n" >> "$LOG_FILE"
        exit 1
    fi
    echo "Repository checked out successfully.\n" >> "$LOG_FILE"
fi

# Log the commit information
echo "Commit to $REPO_PATH at revision $REVISION\n" >> "$LOG_FILE"

# Update the working copy
svn update --username "$USERNAME" --password "$PASSWORD" --non-interactive --verbose --accept "$ACCEPT_CHOICE" "$WORKING_COPY" >> "$LOG_FILE" 2>&1

# Wait for user input before exiting
read -p "Press enter to exit..." input
