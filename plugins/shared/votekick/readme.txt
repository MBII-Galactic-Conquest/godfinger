==============================================================================
VOTEKICK PLUGIN FOR GODFINGER
Authored by 2cwldys
==============================================================================

DESCRIPTION:
VoteKick allows players to vote to temporarily ban (tempban) another player
from the server. When enough players vote YES, the target player is tempbanned
for a configurable number of rounds.

FEATURES:
- Player-initiated voting with !votekick <player>
- Simple voting with !1 (yes) and !2 (no)
- Non-voters count as NO votes
- Configurable majority threshold (percentage needed to pass)
- Configurable minimum participation (percentage who must vote)
- Configurable vote duration (timeout)
- Configurable tempban punishment (rounds)
- Configurable cooldown between votes
- SMOD admin override command (!overridevotekick)
- Vote conflict prevention (won't overlap with RTV or VoteMute)
- Silent mode for stealth enforcement
- Vote cancels if target disconnects
- SMOD protection (logged-in SMODs cannot be votekicked)
- IP whitelist protection (configurable list of protected IPs)

==============================================================================
INSTALLATION
==============================================================================

1. Ensure the votekick plugin directory is in: plugins/shared/votekick/

2. Add the plugin to your godfingerCfg.json in the "Plugins" array:
   {
       "path": "plugins.shared.votekick.votekick"
   }

3. Configure the plugin by editing plugins/shared/votekick/votekickCfg.json
   (auto-created with defaults on first run)

4. Restart Godfinger

==============================================================================
CONFIGURATION (votekickCfg.json)
==============================================================================

{
    "enabled": true,
    "majorityThreshold": 0.75,
    "minimumParticipation": 0.5,
    "voteDuration": 60,
    "tempbanRounds": 3,
    "voteCooldown": 120,
    "silentMode": false,
    "messagePrefix": "^1[VoteKick]^7: ",
    "protectSmods": true,
    "protectedIPsFile": "protectedIPs.txt"
}

PARAMETERS:

enabled (bool):
  Master switch to enable/disable the plugin entirely
  Default: true

majorityThreshold (float):
  Percentage of TOTAL players needed to vote YES for the vote to pass
  0.75 = 75% of all players must vote YES
  Example: 10 players online, 8 must vote YES to pass
  Default: 0.75

minimumParticipation (float):
  Percentage of TOTAL players who must vote (YES or NO) for vote to be valid
  0.5 = 50% of all players must participate
  If participation is below this threshold, vote fails
  Example: 10 players online, 5 must vote for vote to be valid
  Default: 0.5

voteDuration (int):
  Duration in SECONDS before vote ends
  Default: 60

tempbanRounds (int):
  Number of ROUNDS to tempban player on successful vote
  Default: 3

voteCooldown (int):
  Duration in SECONDS before another votekick can be started
  Cooldown applies after any vote ends (pass or fail)
  Default: 120

silentMode (bool):
  If true: No chat announcements
  If false: Announce vote progress and results
  Default: false

messagePrefix (string):
  Prefix for server messages (supports MB2 color codes)
  Default: "^1[VoteKick]^7: "

protectSmods (bool):
  If true: Logged-in SMODs cannot be votekicked
  If false: SMODs can be votekicked like any other player
  Default: true

protectedIPsFile (string):
  Path to a text file containing protected IP addresses (one per line)
  Players connecting from these IPs are immune to votekick
  Supports both absolute paths and relative paths (relative to plugin directory)
  Lines starting with # are treated as comments
  Example file contents:
    # Admin IPs
    192.168.1.100
    10.0.0.50
  Default: "protectedIPs.txt"

==============================================================================
PLAYER COMMANDS
==============================================================================

!votekick <player> | !vk <player>
  Description: Start a vote to kick (tempban) a player
  Usage: !votekick Badplayer
  Notes:
  - Player name is case-insensitive and supports partial matching
  - Cannot votekick yourself
  - Cannot votekick logged-in SMODs (if protectSmods is true)
  - Cannot votekick players with protected IPs (if in protectedIPs list)
  - Cannot start if another vote is in progress (RTV, VoteMute, etc.)
  - Cannot start if votekick is on cooldown

!1
  Description: Vote YES on active votekick
  Notes: Only works when a votekick is in progress

!2
  Description: Vote NO on active votekick
  Notes: Only works when a votekick is in progress

==============================================================================
SMOD ADMIN COMMANDS
==============================================================================

!overridevotekick <1|2> | !ovk <1|2>
  Description: Override active votekick as admin
  Permissions: SMOD only
  Usage: /smod smsay !overridevotekick 1  (force pass)
         /smod smsay !overridevotekick 2  (force fail)
  Notes:
  - Use to prevent abuse or trolling
  - Immediately ends the vote with specified result
  - 1 = Force vote to PASS (target gets tempbanned)
  - 2 = Force vote to FAIL (target is not punished)

!togglevotekick | !tvk
  Description: Enable or disable votekick on the fly
  Permissions: SMOD only
  Usage: /smod smsay !togglevotekick
  Notes:
  - Toggles votekick availability for players
  - If a vote is in progress when disabling, it is cancelled
  - State persists until toggled again or server restart
  - Initial state is determined by "enabled" in config

These commands will appear in the SMOD help menu when you type:
  /smod smsay !help

==============================================================================
HOW IT WORKS
==============================================================================

VOTE FLOW:

1. Player types !votekick <playername>
2. Plugin finds target player by name (partial match allowed)
3. Vote starts:
   - Initiator automatically votes YES
   - Announcement sent: "X started a vote to KICK Y. Type !1 for YES, !2 for NO"
   - Vote registered in votesInProgress (prevents other votes)

4. During vote:
   - Players type !1 to vote YES
   - Players type !2 to vote NO
   - Players can change their vote
   - Progress announced on each YES vote

5. Vote ends when:
   - Time expires (voteDuration seconds)
   - OR enough YES votes are reached (majorityThreshold)
   - OR target disconnects (vote cancelled)
   - OR admin uses !overridevote

6. Vote result:
   - PASS: Target is tempbanned for tempbanRounds
   - FAIL: Not enough YES votes
   - INSUFFICIENT: Not enough participation (below minimumParticipation)

7. Cooldown starts (voteCooldown seconds)

==============================================================================
VOTE CONFLICT PREVENTION
==============================================================================

VoteKick uses the "votesInProgress" server variable to prevent conflicts:

- Cannot start votekick if RTV is in progress
- Cannot start votekick if VoteMute is in progress
- RTV cannot start if votekick is in progress
- VoteMute cannot start if votekick is in progress

This ensures only one vote happens at a time across all voting plugins.

==============================================================================
USE CASES
==============================================================================

SCENARIO 1: Standard VoteKick (Default)
  Config: majorityThreshold=0.75, minimumParticipation=0.5, tempbanRounds=3
  Players: 10 online
  Result: Needs 8 YES votes AND 5 total voters to pass
  Punishment: 3 round tempban

SCENARIO 2: Strict VoteKick
  Config: majorityThreshold=0.9, minimumParticipation=0.6, tempbanRounds=5
  Players: 10 online
  Result: Needs 9 YES votes AND 6 total voters to pass
  Punishment: 5 round tempban

SCENARIO 3: Lenient VoteKick
  Config: majorityThreshold=0.51, minimumParticipation=0.3, tempbanRounds=1
  Players: 10 online
  Result: Needs 6 YES votes AND 3 total voters to pass
  Punishment: 1 round tempban

==============================================================================
TROUBLESHOOTING
==============================================================================

VOTE NOT STARTING:
- Check "enabled": true in votekickCfg.json
- Check if another vote is in progress (RTV, VoteMute)
- Check if votekick is on cooldown
- Verify player name matches (partial match required)
- Check if target is a logged-in SMOD (protected by default)
- Check if target IP is in protectedIPs list

VOTES NOT COUNTING:
- Ensure players are typing !1 or !2 (not 1 or 2 without !)
- Check if vote has already ended

TEMPBAN NOT APPLYING:
- Check Godfinger logs for errors
- Verify server has tempban command available

CONFLICT WITH RTV:
- Both plugins check votesInProgress variable
- If conflict occurs, restart Godfinger to clear state

==============================================================================
TECHNICAL DETAILS
==============================================================================

FILES:
- votekick.py: Main plugin code
- votekickCfg.json: Configuration (auto-created, gitignored)
- protectedIPs.txt: List of protected IP addresses (create manually if needed)
- readme.txt: This documentation

EVENTS HANDLED:
- GODFINGER_EVENT_TYPE_MESSAGE: Chat commands (!votekick, !1, !2)
- GODFINGER_EVENT_TYPE_SMSAY: SMOD commands (!overridevotekick, !togglevotekick)
- GODFINGER_EVENT_TYPE_CLIENTDISCONNECT: Cancel vote if target leaves
- GODFINGER_EVENT_TYPE_SMOD_LOGIN: Track SMOD logins for protection
- GODFINGER_EVENT_TYPE_SMOD_COMMAND: Detect SMOD logout to remove protection

SERVER VARIABLES:
- votesInProgress: Array tracking active votes (shared with RTV, VoteMute)
- registeredCommands: Chat command registration for !help
- registeredSmodCommands: SMOD command registration for !help

PERFORMANCE:
- Minimal CPU usage
- OnLoop checks vote status each tick
- No database connections
- No file I/O during voting

==============================================================================
