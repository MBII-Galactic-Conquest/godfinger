GITHUB COMMIT TRACKING PLUGIN

Tracks latest github commits to specified repositories & branches,
Compares latest commit hashes in dictionary to latest HEAD, including latest commit message,
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
  "refresh_interval": 60
}

============

CREATED BY 2CWLDYS & VICEDICE
UNDER MIT LICENSE