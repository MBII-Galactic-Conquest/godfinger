@echo off

::::::::::::::::::::::::::::::::::::::::::::::::::::::
:: OBSCURES AUTOMATIC HIDDEN UPDATE FILES FROM USER ::
::::::::::::::::::::::::::::::::::::::::::::::::::::::


attrib +h "..\..\update\.update_noinput.py"
attrib +h "..\..\update\.deployments_noinput.py"
attrib +h "..\..\lib\other\.hardrestart.py"