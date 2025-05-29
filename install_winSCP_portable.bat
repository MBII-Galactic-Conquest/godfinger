@echo off
setlocal

:: !! !! !! !! !! !! :: :: :: !! !! !! !! !! !! !! !! ::
:: !! !! !! !! !! !! :: :: :: !! !! !! !! !! !! !! !! ::

:: DO NOT RUN IF YOU DO NOT INTEND TO INSTALL WINSCP  ::

:: !! !! !! !! !! !! :: :: :: !! !! !! !! !! !! !! !! ::
:: !! !! !! !! !! !! :: :: :: !! !! !! !! !! !! !! !! ::

:: ================================================== ::

set /p confirm="Do you wish to install a portable version of WinSCP in your virtual environment? (Y/N): "
if /i "%confirm%" neq "Y" (
    echo Operation cancelled. Portable WinSCP aborted...
    exit /b
)

REM Create a log file to capture all output for debugging
set LOG_FILE=%CD%\install_winscp_portable_log.log
echo Script started at %DATE% %TIME% > "%LOG_FILE%"
echo. >> "%LOG_FILE%"

REM Redirect all subsequent output to the log file
REM This will make all 'echo' and command outputs go to the log file
REM Any output that needs to be seen on screen should be done before this.
call :main_script_logic >> "%LOG_FILE%" 2>&1

echo.
echo WinSCP Portable installation script finished.
echo Check "%LOG_FILE%" for detailed output.
echo.

endlocal
goto :eof

:main_script_logic
REM --- Configuration ---
SET "WINSCP_URL=https://cdn.winscp.net/files/WinSCP-6.5.1-Portable.zip?secure=2iBYjc_nNY82xJh4AZWDgw==,1748513142"
SET "WINSCP_ZIP_FILENAME=WinSCP-6.5.1-Portable.zip"
SET "TARGET_DIR=venv\portable_WinSCP"

echo.
echo --- WinSCP Portable Installation ---
echo.

REM Create the target directory if it doesn't exist
echo Checking/Creating target directory: %TARGET_DIR%
if exist "%TARGET_DIR%\" (
    echo Directory "%TARGET_DIR%" already exists. Skipping creation.
) else (
    mkdir "%TARGET_DIR%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create directory "%TARGET_DIR%". Exiting.
        exit /b 1
    ) else (
        echo Directory "%TARGET_DIR%" created successfully.
    )
)

REM Navigate to the target directory for easier extraction
pushd "%TARGET_DIR%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to navigate to "%TARGET_DIR%". Exiting.
    exit /b 1
)

REM Download the WinSCP Portable ZIP file
echo Downloading WinSCP Portable...
echo This might take a moment.
curl -L --ssl-no-revoke -o "%WINSCP_ZIP_FILENAME%" "%WINSCP_URL%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to download %WINSCP_ZIP_FILENAME%.
    popd
    exit /b 1
)
echo Download complete.

REM Extract the ZIP file
echo Extracting %WINSCP_ZIP_FILENAME% to current directory...
REM Using 'tar' which is built-in on Windows 10+ for .zip extraction
tar -xf "%WINSCP_ZIP_FILENAME%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to extract %WINSCP_ZIP_FILENAME%.
    popd
    exit /b 1
)
echo Extraction complete.

REM Clean up the downloaded ZIP file
echo Cleaning up downloaded ZIP file...
del "%WINSCP_ZIP_FILENAME%"
if %errorlevel% neq 0 (
    echo WARNING: Failed to delete %WINSCP_ZIP_FILENAME%. Please delete it manually.
) else (
    echo Cleanup complete.
)

REM Navigate back to the original directory
popd

echo.
echo WinSCP Portable has been successfully installed to: %CD%\%TARGET_DIR%
echo.
echo You can run WinSCP from: %CD%\%TARGET_DIR%\WinSCP.exe
echo.

exit /b 0