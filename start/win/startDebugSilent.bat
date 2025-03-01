echo off
CD ../../
set "venvp=./venv/Scripts/activate.bat"
if exist "%venvp%" (
    call venv/Scripts/activate.bat
    CD ./update
    python ./update.py
    CD ../
    CALL ./cleanup.bat
    python ./godfinger.py --debug -lf "./bigdata.log"
    PAUSE
) else (
    echo on
    echo Virtual environment does not exist or was created improperly, please run prepare.bat in root dir, aborting.
    PAUSE
)