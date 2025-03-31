@echo off
setlocal

:: !! !! !! !! !! !! :: :: !! !! !! !! !! !! ::
:: !! !! !! !! !! !! :: :: !! !! !! !! !! !! ::

:: DO NOT RUN IF YOU DO NOT INTEND TO INSTALL SVN PORTABLE ::

:: !! !! !! !! !! !! :: :: !! !! !! !! !! !! ::
:: !! !! !! !! !! !! :: :: !! !! !! !! !! !! ::

:: ========================================= ::

set /p confirm="Do you wish to install a portable version of Subversion in your virtual environment? This can override your PATH (Y/N): "
if /i "%confirm%" neq "Y" (
    echo Operation cancelled. Portable SVN install aborted...
    exit /b
)

:: Create a log file to capture all output for debugging
set LOG_FILE=%CD%\install_svnportable_log.log
echo Script started at %DATE% %TIME% > "%LOG_FILE%"

:: Check if SVN is installed by looking for svn.exe in the PATH
echo Checking if SVN portable is installed... >> "%LOG_FILE%"
:: where svn >nul 2>>"%LOG_FILE%"
if not exist %CD%\venv\SVN (
    echo SVN is not installed. Installing SVN... >> "%LOG_FILE%"

    :: Create the directory where SVN will be installed
    set SVN_DIR=%CD%\venv\SVN
    if not exist "%SVN_DIR%" (
        mkdir "%SVN_DIR%"
        echo Created SVN directory: %SVN_DIR% >> "%LOG_FILE%"
    )

    :: Download the SVN zip file from the provided URL
    echo Downloading SVN ZIP file... >> "%LOG_FILE%"
    powershell -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.visualsvn.com/files/Apache-Subversion-1.14.5.zip' -OutFile '%SVN_DIR%\subversion.zip'" >> "%LOG_FILE%" 2>&1
    if %errorlevel% neq 0 (
        echo Error downloading SVN ZIP file. >> "%LOG_FILE%"
        pause
        exit /b
    )

    :: Extract the contents of the zip file
    echo Extracting SVN ZIP file... >> "%LOG_FILE%"
    powershell -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%SVN_DIR%\subversion.zip' -DestinationPath '%SVN_DIR%'" >> "%LOG_FILE%" 2>&1
    if %errorlevel% neq 0 (
        echo Error extracting SVN ZIP file. >> "%LOG_FILE%"
        pause
        exit /b
    )

	:: Delete the ZIP file after extraction
	echo Deleting the SVN ZIP file... >> "%LOG_FILE%"
	del "%SVN_DIR%\subversion.zip" >> "%LOG_FILE%" 2>&1
	if %errorlevel% neq 0 (
		echo Failed to delete the SVN ZIP file. >> "%LOG_FILE%"
		pause
		exit /b
	)

    :: Check if svn.exe exists after extraction
    if not exist "%SVN_DIR%\bin\svn.exe" (
        echo Failed to install SVN. svn.exe not found in the extracted directory. >> "%LOG_FILE%"
        pause
        exit /b
    )

	endlocal
	
	:: Set the SVN environment variable to the folder containing svn.exe
    set SVN_BIN=%SVN_DIR%\bin
    setx PATH "%PATH%;%SVN_BIN%"

    echo SVN installed successfully in %SVN_DIR%\bin. >> "%LOG_FILE%"
) else (
    echo SVN is already installed. >> "%LOG_FILE%"
)

:: Re-check if SVN is now available after installation
where svn >nul 2>>"%LOG_FILE%"
if %errorlevel% neq 0 (
    echo SVN installation failed, still unable to find svn in the PATH. >> "%LOG_FILE%"
    pause
    exit /b
)

echo Install script finished at %DATE% %TIME% >> "%LOG_FILE%"
echo Press enter to exit...
set /p input=
