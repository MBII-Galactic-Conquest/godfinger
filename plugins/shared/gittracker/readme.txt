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
      "branch": "main"
    },
    {
      "repository": "user/repo",
      "branch": "main"
    }
  ],
  "refresh_interval": 60,
  "gfBuildBranch": "main",
  "svnPostHookFile": "path/to/bat/or/sh",
  "isSVNBuilding": false,
  "isGFBuilding": false
}

IF you are using SVN building with a post hook file, ensure it is in godfinger RWD.

============

CREATED BY 2CWLDYS & VICEDICE
UNDER MIT LICENSE