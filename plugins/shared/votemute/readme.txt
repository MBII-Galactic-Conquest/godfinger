==============================================================================
VOTEMUTE PLUGIN FOR GODFINGER
Authored by 2cwldys
==============================================================================

DESCRIPTION:
VoteMute allows players to vote to mute another player on the server.
When enough players vote YES, the target player is muted for a configurable
number of minutes.

FEATURES:
- Player-initiated voting with !votemute <player>
- Simple voting with !1 (yes) and !2 (no)
- Non-voters count as NO votes
- Configurable majority threshold (percentage needed to pass)
- Configurable minimum participation (percentage who must vote)
- Configurable vote duration (timeout)
- Configurable mute punishment (minutes)
- Configurable cooldown between votes
- SMOD admin override command (!overridevote)
- Vote conflict prevention (won't overlap with RTV or VoteKick)
- Silent mode for stealth enforcement
- Vote cancels if target disconnects

==============================================================================
INSTALLATION
==============================================================================

1. Ensure the votemute plugin directory is in: plugins/shared/votemute/

2. Add the plugin to your godfingerCfg.json in the "Plugins" array:
   {
       "path": "plugins.shared.votemute.votemute"
   }

3. Configure the plugin by editing plugins/shared/votemute/votemuteCfg.json
   (auto-created with defaults on first run)

4. Restart Godfinger

==============================================================================
CONFIGURATION (votemuteCfg.json)
==============================================================================

{
    "enabled": true,
    "majorityThreshold": 0.75,
    "minimumParticipation": 0.5,
    "voteDuration": 60,
    "muteDuration": 15,
    "voteCooldown": 120,
    "silentMode": false,
    "messagePrefix": "^5[VoteMute]^7: "
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

muteDuration (int):
  Duration in MINUTES to mute player on successful vote
  Default: 15

voteCooldown (int):
  Duration in SECONDS before another votemute can be started
  Cooldown applies after any vote ends (pass or fail)
  Default: 120

silentMode (bool):
  If true: No chat announcements
  If false: Announce vote progress and results
  Default: false

messagePrefix (string):
  Prefix for server messages (supports MB2 color codes)
  Default: "^5[VoteMute]^7: "

==============================================================================
PLAYER COMMANDS
==============================================================================

!votemute <player> | !vm <player>
  Description: Start a vote to mute a player
  Usage: !votemute Spammer
  Notes:
  - Player name is case-insensitive and supports partial matching
  - Cannot votemute yourself
  - Cannot start if another vote is in progress (RTV, VoteKick, etc.)
  - Cannot start if votemute is on cooldown

!1
  Description: Vote YES on active votemute
  Notes: Only works when a votemute is in progress

!2
  Description: Vote NO on active votemute
  Notes: Only works when a votemute is in progress

==============================================================================
SMOD ADMIN COMMANDS
==============================================================================

!overridevotemute <1|2> | !ovm <1|2>
  Description: Override active votemute as admin
  Permissions: SMOD only
  Usage: /smod smsay !overridevotemute 1  (force pass)
         /smod smsay !overridevotemute 2  (force fail)
  Notes:
  - Use to prevent abuse or trolling
  - Immediately ends the vote with specified result
  - 1 = Force vote to PASS (target gets muted)
  - 2 = Force vote to FAIL (target is not punished)

!togglevotemute | !tvm
  Description: Enable or disable votemute on the fly
  Permissions: SMOD only
  Usage: /smod smsay !togglevotemute
  Notes:
  - Toggles votemute availability for players
  - If a vote is in progress when disabling, it is cancelled
  - State persists until toggled again or server restart
  - Initial state is determined by "enabled" in config

These commands will appear in the SMOD help menu when you type:
  /smod smsay !help

==============================================================================
HOW IT WORKS
==============================================================================

VOTE FLOW:

1. Player types !votemute <playername>
2. Plugin finds target player by name (partial match allowed)
3. Vote starts:
   - Initiator automatically votes YES
   - Announcement sent: "X started a vote to MUTE Y. Type !1 for YES, !2 for NO"
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
   - PASS: Target is muted for muteDuration minutes
   - FAIL: Not enough YES votes
   - INSUFFICIENT: Not enough participation (below minimumParticipation)

7. Cooldown starts (voteCooldown seconds)

==============================================================================
VOTE CONFLICT PREVENTION
==============================================================================

VoteMute uses the "votesInProgress" server variable to prevent conflicts:

- Cannot start votemute if RTV is in progress
- Cannot start votemute if VoteKick is in progress
- RTV cannot start if votemute is in progress
- VoteKick cannot start if votemute is in progress

This ensures only one vote happens at a time across all voting plugins.

==============================================================================
USE CASES
==============================================================================

SCENARIO 1: Standard VoteMute (Default)
  Config: majorityThreshold=0.75, minimumParticipation=0.5, muteDuration=15
  Players: 10 online
  Result: Needs 8 YES votes AND 5 total voters to pass
  Punishment: 15 minute mute

SCENARIO 2: Lenient VoteMute
  Config: majorityThreshold=0.51, minimumParticipation=0.3, muteDuration=5
  Players: 10 online
  Result: Needs 6 YES votes AND 3 total voters to pass
  Punishment: 5 minute mute

SCENARIO 3: Strict VoteMute
  Config: majorityThreshold=0.9, minimumParticipation=0.6, muteDuration=30
  Players: 10 online
  Result: Needs 9 YES votes AND 6 total voters to pass
  Punishment: 30 minute mute

==============================================================================
TROUBLESHOOTING
==============================================================================

VOTE NOT STARTING:
- Check "enabled": true in votemuteCfg.json
- Check if another vote is in progress (RTV, VoteKick)
- Check if votemute is on cooldown
- Verify player name matches (partial match required)

VOTES NOT COUNTING:
- Ensure players are typing !1 or !2 (not 1 or 2 without !)
- Check if vote has already ended

MUTE NOT APPLYING:
- Check Godfinger logs for errors
- Verify server has mute command available

CONFLICT WITH RTV/VOTEKICK:
- Both plugins check votesInProgress variable
- If conflict occurs, restart Godfinger to clear state

==============================================================================
TECHNICAL DETAILS
==============================================================================

FILES:
- votemute.py: Main plugin code
- votemuteCfg.json: Configuration (auto-created, gitignored)
- readme.txt: This documentation

EVENTS HANDLED:
- GODFINGER_EVENT_TYPE_MESSAGE: Chat commands (!votemute, !1, !2)
- GODFINGER_EVENT_TYPE_SMSAY: SMOD commands (!overridevote)
- GODFINGER_EVENT_TYPE_CLIENTDISCONNECT: Cancel vote if target leaves

SERVER VARIABLES:
- votesInProgress: Array tracking active votes (shared with RTV, VoteKick)
- registeredCommands: Chat command registration for !help
- registeredSmodCommands: SMOD command registration for !help

PERFORMANCE:
- Minimal CPU usage
- OnLoop checks vote status each tick
- No database connections
- No file I/O during voting

==============================================================================
