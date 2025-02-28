#!/bin/bash

cd ../../
cd ./update
python3	./update.py
cd ../
./cleanup.sh
python3 ./godfinger.py
read -p "Press Enter to continue..."