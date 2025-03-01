#!/bin/bash

echo "Searching for .db files to delete..."

db_found=false

# Find all .db files recursively and delete them
find . -type f -name "*.db" | while read -r db_file; do
    echo "Deleting $db_file"
    rm -f "$db_file"
    db_found=true
done

# Check if any .db files were found
if [ "$db_found" = false ]; then
    echo "No database files to delete."
else
    echo "All .db files in recursive directories have been deleted."
fi

echo "Press enter to exit..."
read -r input