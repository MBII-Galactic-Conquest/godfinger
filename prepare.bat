
set "venvp=./venv/Scripts/activate.bat"
if not exist "%venvp%" (
    python -m venv venv
) 
call venv/Scripts/activate.bat
echo Using python at :
where python
python -m pip install -U -r requirements.txt
START /WAIT python ./prepare.py
echo Press enter to exit... 
set /p input=   