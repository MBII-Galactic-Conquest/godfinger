@echo off
setlocal

:: SVN Repository and Working Copy Paths
set REPO_PATH=%1
set REVISION=%2
set WORKING_COPY="./"
set CONFIG_FILE=svnConfig.json

:: Check if svnConfig.json exists, if not create it with default values
if not exist "%CONFIG_FILE%" (
    echo { > "%CONFIG_FILE%"
    echo "username": "" >> "%CONFIG_FILE%"
    echo "password": "" >> "%CONFIG_FILE%"
    echo "accept_choice": "theirs-full" >> "%CONFIG_FILE%"
    echo } >> "%CONFIG_FILE%"
    echo svnConfig.json created with empty username, password, and default accept_choice.
)

:: Read username, password, and accept_choice from svnConfig.json
for /f "tokens=2 delims=:," %%A in ('findstr /i "username" "%CONFIG_FILE%"') do set USERNAME=%%~A
for /f "tokens=2 delims=:," %%A in ('findstr /i "password" "%CONFIG_FILE%"') do set PASSWORD=%%~A
for /f "tokens=2 delims=:," %%A in ('findstr /i "accept_choice" "%CONFIG_FILE%"') do set ACCEPT_CHOICE=%%~A

:: Trim whitespace and quotes
set USERNAME=%USERNAME:~1,-1%
set PASSWORD=%PASSWORD:~1,-1%
set ACCEPT_CHOICE=%ACCEPT_CHOICE:~1,-1%

:: Log the commit information
echo Commit to %REPO_PATH% at revision %REVISION% >> "./svn_commits.log"

:: Update the working copy
svn update %WORKING_COPY% --username %USERNAME% --password %PASSWORD% --non-interactive --accept %ACCEPT_CHOICE%

echo Press enter to exit...
set /p input=