#!/bin/bash

../../cleanup.sh
cd ../../
python3 ./godfinger.py -lf "./bigdata.log"
read -p "Press Enter to continue..."
