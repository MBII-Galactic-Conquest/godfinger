#!/bin/bash
if ! test -f venv/Scripts/activate; then
    python -m venv venv
fi
source venv/Scripts/activate
echo Using python at
which python
python -m pip install -U -r requirements.txt
python ./prepare.py
echo "Press enter to exit..."
read input