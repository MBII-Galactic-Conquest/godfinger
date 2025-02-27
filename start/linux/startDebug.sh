#!/bin/bash

../../cleanup.sh
cd ../../
python3 ./godfinger.py --debug
read -p "Press Enter to continue..."
