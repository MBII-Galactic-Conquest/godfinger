@echo off
setlocal enabledelayedexpansion

:: Initialize a flag to track if __pycache__ directories are found
set "found=0"

:: Search for any __pycache__ directories
for /d /r %%d in (__pycache__) do (
    set "found=1"
)

:: If no __pycache__ folders were found, print the message and exit
if !found! == 0 (
    echo No __pycache__ folders detected for cleanup.
    goto :end
)

:: If __pycache__ folders are found, proceed with deletion
:delete
:: Delete all __pycache__ folders if found
for /d /r %%d in (__pycache__) do (
    if exist "%%d" (
        echo Deleting: "%%d"
        rmdir /s /q "%%d"
    )
)

echo Cleanup complete.

:end
endlocal
echo Press enter to continue...
set /p input=
