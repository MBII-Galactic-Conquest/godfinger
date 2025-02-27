#!/bin/bash

cd ../../
./cleanup.sh
python3 ./godfinger.py --debug
read -p "Press Enter to continue..."
