@echo off

:: Navigate to the parent directory and then to ./bin
cd ../
cd bin 2>nul || goto bin_missing

:: Check if Python 3 is installed, fallback to Python
where python3 >nul 2>nul
if %errorlevel% == 0 (
    set PYTHON_CMD=python
    set PIP_CMD=pip
) else (
    where python >nul 2>nul
    if %errorlevel% == 0 (
        set PYTHON_CMD=python
        set PIP_CMD=pip
    ) else (
        echo Error: Python is not installed.
        pause
        exit /b
    )
)

:: Install dependencies
echo Installing dependencies...
%PIP_CMD% install -U -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing dependencies. Press Enter to exit.
    pause
    exit /b
)

:: Run the prepare.py script
echo Running prepare.py...
START /WAIT %PYTHON_CMD% ./prepare.py
if %errorlevel% neq 0 (
    echo Error running prepare.py. Press Enter to exit.
    pause
    exit /b
)

:: Wait for user input before exiting
goto end

:bin_missing
echo Bin folder does not exist. Press Enter to continue...
pause >nul
goto end

:end
echo Press Enter to exit...
set /p input=
