#!/bin/bash

cd ../../
./cleanup.sh
python3 ./godfinger.py
read -p "Press Enter to continue..."