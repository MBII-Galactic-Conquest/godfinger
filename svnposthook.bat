@echo off
setlocal enabledelayedexpansion

:::::::::::::::::::::::::::::::::::::::::::::::::
:: ENSURE SVN IS INSTALLED ON YOUR SYSTEM PATH ::
:::::::::::::::::::::::::::::::::::::::::::::::::

:: Create a log file to capture all output for debugging
set LOG_FILE=%CD%\svn_update_log.log
echo svnposthook.bat started at %DATE% %TIME% > "%LOG_FILE%"

:: SVN Repository and Working Copy Paths
set WORKING_COPY=%CD%
set CONFIG_FILE=svnConfig.json

:: Check if svnConfig.json exists, if not create it with default values
if not exist "%CONFIG_FILE%" (
    echo {> "%CONFIG_FILE%"
	echo "repo_path": "">> "%CONFIG_FILE%"
	echo "revision": "">> "%CONFIG_FILE%"
    echo "username": "">> "%CONFIG_FILE%"
    echo "password": "">> "%CONFIG_FILE%"
    echo "accept_choice": "theirs-full">> "%CONFIG_FILE%"
    echo }>> "%CONFIG_FILE%"
    echo svnConfig.json created with empty username, password, and default accept_choice. >> "%LOG_FILE%"
)

:: Read username, password, and accept_choice from svnConfig.json
for /f "tokens=2 delims=:," %%A in ('findstr /i "repo_path" "%CONFIG_FILE%"') do set REPO_PATH=%%~A
for /f "tokens=2 delims=:," %%A in ('findstr /i "revision" "%CONFIG_FILE%"') do set REVISION=%%~A
for /f "tokens=2 delims=:," %%A in ('findstr /i "username" "%CONFIG_FILE%"') do set USERNAME=%%~A
for /f "tokens=2 delims=:," %%A in ('findstr /i "password" "%CONFIG_FILE%"') do set PASSWORD=%%~A
for /f "tokens=2 delims=:," %%A in ('findstr /i "accept_choice" "%CONFIG_FILE%"') do set ACCEPT_CHOICE=%%~A

:: Trim whitespace and quotes
set REPO_PATH=%REPO_PATH%
set REVISION=%REVISION%
set USERNAME=%USERNAME%
set PASSWORD=%PASSWORD%
set ACCEPT_CHOICE=%ACCEPT_CHOICE%

:: Check if .svn folder exists in the current directory
if not exist "%WORKING_COPY%\.svn" (
    echo The working copy is not checked out. > "%LOG_FILE%"
    
    :: Checkout the repository from %REPO_PATH% at %REVISION%
    echo Checking out repository %REPO_PATH% at revision %REVISION%... >> "%LOG_FILE%"
    svn checkout --username %USERNAME% --password %PASSWORD% --non-interactive --verbose %REPO_PATH% %WORKING_COPY% >> "%LOG_FILE%" 2>&1
    if %errorlevel% neq 0 (
        echo Checkout failed. Please check the repository URL, revision, or your credentials. >> "%LOG_FILE%"
        exit /b
    )
    echo Repository checked out successfully. >> "%LOG_FILE%"
)

:: Log the commit information
echo Commit to %REPO_PATH% at revision %REVISION% >> "%LOG_FILE%"

:: Update the working copy
svn update --username %USERNAME% --password %PASSWORD% --non-interactive --verbose --accept %ACCEPT_CHOICE% %WORKING_COPY% >> "%LOG_FILE%" 2>&1

echo Press enter to exit...
set /p input=
