echo Configuring virtual environment, please wait...
@echo off

:: Navigate to the parent directory and then to ./bin
cd ../
cd bin 2>nul || goto bin_missing

set "venvp=../../venv/Scripts/activate.bat"
if not exist "%venvp%" (
    python -m venv ../../venv
) 
call ../../venv/Scripts/activate.bat
echo Using python at :
where python

:: Install dependencies
echo Installing dependencies...
python -m pip install -U -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing dependencies. Press Enter to exit.
    pause
    exit /b
)

:: Run the prepare.py script
echo Running ANSI-WIN1252 file-read-backwards patch...
START /WAIT python ./prepare.py
if %errorlevel% neq 0 (
    echo Error running prepare.py. Press Enter to exit.
    pause
    exit /b
)

:: Check if MSVC.x86 is installed
echo Verifying MSVC.x86 installation for MBII dedicated binaries...
START /WAIT python ./msvc_win.py
if %errorlevel% neq 0 (
    echo Error running msvc_win.py. Press Enter to exit.
    pause
    exit /b
)

:: Run the noinput obscuring script
echo Obscuring update and deployments noinput files, as they are not intended to be used...
call ./obscure_win.bat
if %errorlevel% neq 0 (
    echo Error running obscure_win.bat. Press Enter to exit.
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
