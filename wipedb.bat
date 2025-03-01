@echo off
echo Searching for .db files to delete...

set db_found=false

for /r %%f in (*.db) do (
    echo Deleting %%f
    del "%%f"
    set db_found=true
)

if not %db_found%==true (
    echo No database files to delete.
) else (
    echo All .db files in recursive directories have been deleted.
)

echo Press enter to exit...
set /p input=
