==============================================================================
VOTETEAMSWAP PLUGIN FOR GODFINGER
Authored by 2cwldys
==============================================================================

DESCRIPTION:
VoteTeamSwap allows players to vote to toggle the g_teamSwap server cvar.
When enough players vote YES, the team swap setting is enabled or disabled.

FEATURES:
- Player-initiated voting with !voteteamswap
- Simple voting with !1 (yes) and !2 (no)
- Non-voters count as NO votes
- Configurable majority threshold (percentage needed to pass)
- Configurable minimum participation (percentage who must vote)
- Configurable vote duration (timeout)
- Configurable cooldown between votes
- SMOD admin override command (!overridevoteteamswap)
- Vote conflict prevention (won't overlap with RTV, VoteKick, or VoteMute)
- Silent mode for stealth enforcement
- Automatic toggle behavior (votes to enable if disabled, disable if enabled)

==============================================================================
INSTALLATION
==============================================================================

1. Ensure the voteteamswap plugin directory is in: plugins/shared/voteteamswap/

2. Add the plugin to your godfingerCfg.json in the "Plugins" array:
   {
       "path": "plugins.shared.voteteamswap.voteteamswap"
   }

3. Configure the plugin by editing plugins/shared/voteteamswap/voteteamswapCfg.json
   (auto-created with defaults on first run)

4. Restart Godfinger

==============================================================================
CONFIGURATION (voteteamswapCfg.json)
==============================================================================

{
    "enabled": true,
    "majorityThreshold": 0.75,
    "minimumParticipation": 0.5,
    "voteDuration": 60,
    "voteCooldown": 120,
    "silentMode": false,
    "messagePrefix": "^3[VoteTeamSwap]^7: "
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

voteCooldown (int):
  Duration in SECONDS before another voteteamswap can be started
  Cooldown applies after any vote ends (pass or fail)
  Default: 120

silentMode (bool):
  If true: No chat announcements
  If false: Announce vote progress and results
  Default: false

messagePrefix (string):
  Prefix for server messages (supports MB2 color codes)
  Default: "^3[VoteTeamSwap]^7: "

==============================================================================
PLAYER COMMANDS
==============================================================================

!voteteamswap | !vts
  Description: Start a vote to toggle team swap
  Usage: !voteteamswap
  Notes:
  - Automatically determines current g_teamSwap state
  - Votes to ENABLE if currently disabled (0)
  - Votes to DISABLE if currently enabled (1)
  - Cannot start if another vote is in progress (RTV, VoteKick, VoteMute)
  - Cannot start if voteteamswap is on cooldown

!1
  Description: Vote YES on active voteteamswap
  Notes: Only works when a voteteamswap is in progress

!2
  Description: Vote NO on active voteteamswap
  Notes: Only works when a voteteamswap is in progress

==============================================================================
SMOD ADMIN COMMANDS
==============================================================================

!overridevoteteamswap <1|2> | !ovts <1|2>
  Description: Override active voteteamswap as admin
  Permissions: SMOD only
  Usage: /smod smsay !overridevoteteamswap 1  (force pass)
         /smod smsay !overridevoteteamswap 2  (force fail)
  Notes:
  - Use to prevent abuse or trolling
  - Immediately ends the vote with specified result
  - 1 = Force vote to PASS (g_teamSwap is changed)
  - 2 = Force vote to FAIL (g_teamSwap remains unchanged)

!togglevoteteamswap | !tvts
  Description: Enable or disable voteteamswap on the fly
  Permissions: SMOD only
  Usage: /smod smsay !togglevoteteamswap
  Notes:
  - Toggles voteteamswap availability for players
  - If a vote is in progress when disabling, it is cancelled
  - State persists until toggled again or server restart
  - Initial state is determined by "enabled" in config

These commands will appear in the SMOD help menu when you type:
  /smod smsay !help

==============================================================================
HOW IT WORKS
==============================================================================

VOTE FLOW:

1. Player types !voteteamswap
2. Plugin checks current g_teamSwap value
3. Vote starts:
   - If g_teamSwap=0: Vote to ENABLE (set to 1)
   - If g_teamSwap=1: Vote to DISABLE (set to 0)
   - Initiator automatically votes YES
   - Announcement sent: "X started a vote to ENABLE/DISABLE team swap"
   - Vote registered in votesInProgress (prevents other votes)

4. During vote:
   - Players type !1 to vote YES
   - Players type !2 to vote NO
   - Players can change their vote
   - Progress announced on each YES vote

5. Vote ends when:
   - Time expires (voteDuration seconds)
   - OR enough YES votes are reached (majorityThreshold)
   - OR admin uses !overridevoteteamswap

6. Vote result:
   - PASS: g_teamSwap is set to target value
   - FAIL: Not enough YES votes
   - INSUFFICIENT: Not enough participation (below minimumParticipation)

7. Cooldown starts (voteCooldown seconds)

==============================================================================
VOTE CONFLICT PREVENTION
==============================================================================

VoteTeamSwap uses the "votesInProgress" server variable to prevent conflicts:

- Cannot start voteteamswap if RTV is in progress
- Cannot start voteteamswap if VoteKick is in progress
- Cannot start voteteamswap if VoteMute is in progress
- RTV cannot start if voteteamswap is in progress
- VoteKick cannot start if voteteamswap is in progress
- VoteMute cannot start if voteteamswap is in progress

This ensures only one vote happens at a time across all voting plugins.

==============================================================================
USE CASES
==============================================================================

SCENARIO 1: Standard VoteTeamSwap (Default)
  Config: majorityThreshold=0.75, minimumParticipation=0.5
  Players: 10 online
  Result: Needs 8 YES votes AND 5 total voters to pass

SCENARIO 2: Strict VoteTeamSwap
  Config: majorityThreshold=0.9, minimumParticipation=0.6
  Players: 10 online
  Result: Needs 9 YES votes AND 6 total voters to pass

SCENARIO 3: Lenient VoteTeamSwap
  Config: majorityThreshold=0.51, minimumParticipation=0.3
  Players: 10 online
  Result: Needs 6 YES votes AND 3 total voters to pass

==============================================================================
TROUBLESHOOTING
==============================================================================

VOTE NOT STARTING:
- Check "enabled": true in voteteamswapCfg.json
- Check if another vote is in progress (RTV, VoteKick, VoteMute)
- Check if voteteamswap is on cooldown

VOTES NOT COUNTING:
- Ensure players are typing !1 or !2 (not 1 or 2 without !)
- Check if vote has already ended

g_teamSwap NOT CHANGING:
- Check Godfinger logs for errors
- Verify server accepts the g_teamSwap cvar
- Ensure RCON connection is working

CONFLICT WITH OTHER VOTES:
- All vote plugins check votesInProgress variable
- If conflict occurs, restart Godfinger to clear state

==============================================================================
TECHNICAL DETAILS
==============================================================================

FILES:
- voteteamswap.py: Main plugin code
- voteteamswapCfg.json: Configuration (auto-created, gitignored)
- readme.txt: This documentation

EVENTS HANDLED:
- GODFINGER_EVENT_TYPE_MESSAGE: Chat commands (!voteteamswap, !1, !2)
- GODFINGER_EVENT_TYPE_SMSAY: SMOD commands (!overridevoteteamswap, !togglevoteteamswap)

SERVER VARIABLES:
- votesInProgress: Array tracking active votes (shared with RTV, VoteKick, VoteMute)
- registeredCommands: Chat command registration for !help
- registeredSmodCommands: SMOD command registration for !help

CVAR MANIPULATION:
- Uses interface.GetCvar("g_teamSwap") to check current state
- Uses interface.SetCvar("g_teamSwap", "0"|"1") to apply changes

PERFORMANCE:
- Minimal CPU usage
- OnLoop checks vote status each tick
- No database connections
- Single RCON call to set cvar on vote pass

==============================================================================
