Created by 2cwldys
===================

A discord bot plugin that runs in sync with your godfinger installation, allowing pick up game services for JKA.

https://discord.com/developers/

NOTE: Sessions will not start if the player-vs-player ratio is uneven. (!= 3v4, 5v6, etc...)

Type !queue for a readout of commands:

!queue join - join, or create a PUG queue
!queue leave - leave the PUG queue
!queue start - when minimum players are reached, it checks for equal divisible ratios (4v4, 5v5, 6v6...) and allows players to begin the PUG session without an admin present.
!queue status - readout of the current queue status, and involved players in queue.
!queue forcestart - this allows PUG Mods/Captains to forcefully start the queue.
!password|!pw - obtain the PUG password.


pugConfig.env

# Queue Configuration
QUEUE_TIMEOUT=1800  # 30 minutes in seconds
MAX_QUEUE_SIZE=10 <--- Maximum to start a queue is a 5v5.
MIN_QUEUE_SIZE=6 <--- Minimum to start a queue is a 3v3.

# Discord Configuration
BOT_TOKEN= <--- Your BOT access TOKEN, keep private!
PUG_ROLE_ID= <--- Role to PING for when queues start.
ADMIN_ROLE_ID= <--- PUG Mod/Admin role for overriding queues.
ALLOWED_CHANNEL_ID= <--- Required channel ID where PUG queues are handled.
SERVER_PASSWORD=password <--- Change to your sessions password.
