@echo off
setlocal enabledelayedexpansion

:: Ask the user for confirmation (this will be skipped if piped input is provided)
set /p choice=Do you wish to do __pycache__ cleanup? This can prevent conflicts. (Y/N): 

:: Convert the input to lowercase (if it was lowercase or uppercase)
set choice=%choice:~0,1%
set choice=!choice: =!

:: Check if the input is "y" or "n" (case-insensitive)
if /i "%choice%" neq "y" (
    echo Pycache cleanup aborted.
    goto :end
)

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
for /d /r %%d in (__pycache__) do (
    if exist "%%d" (
        echo Deleting: "%%d"
        rmdir /s /q "%%d"
    )
)

echo.
echo Pycache cleanup complete.
echo __pycache__ folders should be regularly emptied after each session.

:end
endlocal
