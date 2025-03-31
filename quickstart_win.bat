@echo off

:::::::::::::::::::::::::::::::::::::::::::::::::
:: ALLOWS QUICK GODFINGER START WITHOUT INPUTS ::
:::::::::::::::::::::::::::::::::::::::::::::::::

cd %CD%

:: Run cleanup.bat with predefined input (Y)
(
    echo Y
) | cmd /c cleanup.bat

:: Add a small delay before running cleanup.bat
timeout /t 1 >nul

:: Save the current directory and change to start\win
pushd "%CD%\start\win\"

:: Run startDebugSilent.bat with predefined input (N)
(
    echo N
) | cmd /c startDebugSilent.bat

:: Return to the original directory (godfinger root)
popd
