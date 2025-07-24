GITHUB COMMIT TRACKING PLUGIN

Tracks latest github commits to specified repositories & branches,
Compares latest commit hashes in dictionary to latest HEAD, including latest commit message,
Automatically deploys godfinger system updates when detected, if 0 players are found in server,
Writes to svsay through rcon when commits are found when monitored.

Users are now informed when you work on anything, in the event they are playing on your server.

ENSURE YOU MODIFY YOUR gtConfig.json,

{
  "repositories": [
    {
      "repository": "user/repo",
      "branch": "main",
      "token": "None"
    },
    {
      "repository": "user/repo",
      "branch": "main",
      "token": "None"
    }
  ],
  "refresh_interval": 60,
  "gfBuildBranch": "main",
  "svnPostHookFile": "path/to/bat/or/sh",
  "winSCPScriptFile": "path/to/bat/or/sh",
  "isWinSCPBuilding": false,
  "isSVNBuilding": false,
  "isGFBuilding": false
}

IF you are using SVN building with a post hook file, ensure it is in godfinger RWD.
IF you are using WinSCP script hooks, for automated .PK3 asset updates, align your gamedata/ folder appropriately.

============

CREATED BY 2CWLDYS & VICEDICE
UNDER MIT LICENSE