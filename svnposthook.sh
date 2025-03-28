# Linux Shell Script (post-commit.sh)
#!/bin/bash

# SVN Repository and Working Copy Paths
REPO_PATH="$1"
REVISION="$2"
WORKING_COPY="./"
ACCEPT_CHOICE="theirs-full"
USERNAME=""
PASSWORD=""

# Log the commit information
echo "Commit to $REPO_PATH at revision $REVISION" >> ./svn_post_commit.log

# Update the working copy
svn update "$WORKING_COPY" --username "$USERNAME" --password "$PASSWORD" --non-interactive --accept "$ACCEPT_CHOICE"

exit 0