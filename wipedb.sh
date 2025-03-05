#!/bin/bash

# DO NOT USE UNLESS YOU INTEND TO MASS PURGE DATABASE FILES!

read -p "Do you wish to clear all recursive directories of all *.db files? (Y/N): " confirm

confirm=$(echo "$confirm" | tr 'a-z' 'A-Z')

if [ "$confirm" != "Y" ]; then
    echo "Operation cancelled. No database files were deleted."
    exit 0
fi

echo "Searching for .db files to delete..."
db_found=false

find . -type f -name "*.db" | while read -r db_file; do
    echo "Deleting $db_file"
    rm -f "$db_file"
    db_found=true
done

if [ "$db_found" = false ]; then
    echo "No database files to delete."
else
    echo "All .db files in recursive directories have been deleted."
fi

read -p "Press enter to exit..." input
