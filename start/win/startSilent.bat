echo off
REM Check Python version
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Python 3.12+ is required but not found.
    echo Please install Python 3.12 or higher and try again.
    exit /b 1
)
echo off
CD ../../
set "venvp=./venv/Scripts/activate.bat"
if exist "%venvp%" (
    call venv/Scripts/activate.bat
    CD ./update
    python ./update.py
    CD ../
    CALL ./cleanup.bat
    python ./godfinger.py -lf "./bigdata.log"
    PAUSE
) else (
    echo on
    echo Virtual environment does not exist or was created improperly, please run prepare.bat in root dir, aborting.
    PAUSE
)

