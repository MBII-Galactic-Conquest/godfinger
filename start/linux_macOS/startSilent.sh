#!/bin/bash
cd ../../
if test -f venv/Scripts/activate; then
    source venv/Scripts/activate
    cd ./update
    python3 ./update.py
    cd ../
    ./cleanup.sh
    python3 ./godfinger.py -lf "./bigdata.log"
    read -p "Press Enter to continue..."
else
    echo on
    echo Virtual environment does not exist or was created improperly, please run prepare.bat in root dir, aborting.
    echo "Press enter to exit..."
    read input
fi
