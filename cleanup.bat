@echo off
setlocal enabledelayedexpansion

:: Ask the user for confirmation
set /p choice=Do you wish to do __pycache__ cleanup? This can prevent conflicts. (Y/N): 

:: Convert input to uppercase to handle lowercase input as well
set choice=!choice:A=a!
set choice=!choice:B=b!
set choice=!choice:C=c!
set choice=!choice:D=d!
set choice=!choice:E=e!
set choice=!choice:F=f!
set choice=!choice:G=g!
set choice=!choice:H=h!
set choice=!choice:I=i!
set choice=!choice:J=j!
set choice=!choice:K=k!
set choice=!choice:L=l!
set choice=!choice:M=m!
set choice=!choice:N=n!
set choice=!choice:O=o!
set choice=!choice:P=p!
set choice=!choice:Q=q!
set choice=!choice:R=r!
set choice=!choice:S=s!
set choice=!choice:T=t!
set choice=!choice:U=u!
set choice=!choice:V=v!
set choice=!choice:W=w!
set choice=!choice:X=x!
set choice=!choice:Y=y!
set choice=!choice:Z=z!

if not "!choice!" == "y" (
    echo Pycache cleanup aborted.
    goto :end
)

:: Initialize a flag to track if __pycache__ directories are found
set "found=0"

:: Search for any __pycache__ directories
for /d /r %%d in (__pycache__) do (
    set "found=1"
)

:: If no __pycache__ folders were found, print the message and exit
if !found! == 0 (
    echo No __pycache__ folders detected for cleanup.
    goto :end
)

:: If __pycache__ folders are found, proceed with deletion
:delete
for /d /r %%d in (__pycache__) do (
    if exist "%%d" (
        echo Deleting: "%%d"
        rmdir /s /q "%%d"
    )
)

echo.
echo Pycache cleanup complete.
echo __pycache__ folders should be regularly emptied after each session.

:end
endlocal
