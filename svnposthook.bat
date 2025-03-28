# Windows Batch Script (post-commit.bat)
@echo off
setlocal

:: SVN Repository and Working Copy Paths
set REPO_PATH=%1
set REVISION=%2
set WORKING_COPY="./"
set ACCEPT_CHOICE="theirs-full"
set USERNAME=""
set PASSWORD=""

:: Log the commit information
echo Commit to %REPO_PATH% at revision %REVISION% >> "./svn_post_commit.log"

:: Update the working copy
svn update %WORKING_COPY% --username %USERNAME% --password %PASSWORD% --non-interactive --accept %ACCEPT_CHOICE%

exit 0