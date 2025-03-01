@echo off

REM Check Python version
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"
IF %ERRORLEVEL% NEQ 0 (
    echo Error: Python 3.12+ is required but not found.
    echo Please install Python 3.12 or higher and try again.
    exit /b 1
)

REM If Python 3.12+ is found, continue with the rest of the commands
CD ../../
CD ./update
PYTHON ./update.py
CD ../
CALL ./cleanup.bat
PYTHON ./godfinger.py -lf "./bigdata.log"
PAUSE
