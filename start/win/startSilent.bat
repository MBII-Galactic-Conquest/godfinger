@echo off

REM Check Python version using `python --version`
for /f "tokens=2 delims= " %%i in ('python --version 2^>^&1') do set python_version=%%i
echo Detected Python version: %python_version%

REM Check if the version is 3.12 or higher (but not 3.11 or lower)
echo %python_version% | findstr /R "^3\.[1-9][2-9]" > nul
if %errorlevel% neq 0 (
    echo Error: Python 3.12+ is required but not found.
    echo Please install Python 3.12 or higher and try again.
    exit /b 1
)

echo Python version is acceptable (3.12.0 or newer)

REM Navigate to bin for autostarting
cd bin

REM Check if MBIIDed.x86.exe is running, start it if not...
python ./autostart_win.py

REM Navigate to the project directory
cd ../../../

REM Set the virtual environment path
set "venvp=./venv/Scripts/activate.bat"

REM Check if the virtual environment exists
if exist "%venvp%" (
    REM Activate the virtual environment
    call venv/Scripts/activate.bat
    cd ./update

    REM Run update script
    python ./update.py
    if %errorlevel% neq 0 (
        echo Error running update.py. Press Enter to exit.
        pause
        exit /b
    )

    REM Go back to root directory
    cd ../

    REM Run cleanup script
    call ./cleanup.bat
    if %errorlevel% neq 0 (
        echo Error running cleanup.bat. Press Enter to exit.
        pause
        exit /b
    )

    REM Run godfinger script
    python ./godfinger.py -lf "./bigdata.log"
    if %errorlevel% neq 0 (
        echo Error running godfinger.py. Press Enter to exit.
        pause
        exit /b
    )

) else (
    REM If the virtual environment doesn't exist
    echo Virtual environment does not exist or was created improperly, please run prepare.bat in root dir, aborting.
    pause
)
