#!/bin/bash

cd ../../
./cleanup.sh
python3 ./godfinger.py --debug -lf "./bigdata.log"
read -p "Press Enter to continue..."