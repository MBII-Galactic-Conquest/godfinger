#!/bin/bash

cd ../../
./cleanup.sh
python3 ./godfinger.py -lf "./bigdata.log"
read -p "Press Enter to continue..."
