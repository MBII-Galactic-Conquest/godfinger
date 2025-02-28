CD ../../
CD ./update
python ./update.py
CD ../
CALL ./cleanup.bat
python ./godfinger.py -lf "./bigdata.log"
PAUSE