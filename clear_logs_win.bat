@echo off
REM clear_logs.bat
REM This script deletes all log files starting with "bigdata.log" in the current directory.
REM This includes 'bigdata.log' and all timestamped backups like 'bigdata.log-10022025_143'.

echo Checking for log files to delete...

REM Use DEL /F /Q to force deletion and suppress confirmation, then use the wildcard.
DEL /F /Q bigdata.log*

IF EXIST bigdata.log (
echo.
echo ERROR: Could not delete some files. They might be in use.
echo.
) ELSE (
echo.
echo Successfully deleted all files matching 'bigdata.log*'.
echo.
)

REM Pause is useful for running the script by double-clicking in Windows,
REM so the user can see the output before the window closes.
pause