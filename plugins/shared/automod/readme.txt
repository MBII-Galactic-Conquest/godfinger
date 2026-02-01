==============================================================================
AUTOMOD PLUGIN FOR GODFINGER
Authored by 2cwldys
==============================================================================

DESCRIPTION:
AutoMod is a chat moderation plugin that monitors all player chat messages
for prohibited words, tracks violations by IP address, and applies
configurable punishments when violation thresholds are reached.

FEATURES:
- Monitors ALL chat types (global, team, say, say_team)
- IP-based violation tracking (persists across name changes)
- Case-insensitive substring matching for prohibited words
- Automatic color code stripping before matching
- Session-based violation counters (reset on map change)
- Persistent violation logging (survives restarts)
- Configurable punishment actions (mute, kick, tempban, ban)
- Silent mode for stealth enforcement
- SMOD admin commands for mass moderation
- Automatic punishment re-application on repeated threshold violations

==============================================================================
INSTALLATION
==============================================================================

1. Ensure the automod plugin directory is in: plugins/shared/automod/

2. Add the plugin to your godfingerCfg.json in the "Plugins" section:
   {
       "enabled": true,
       "module": "plugins.shared.automod.automod"
   }

3. Configure the plugin by editing plugins/shared/automod/automodCfg.json

4. Restart Godfinger

==============================================================================
CONFIGURATION (automodCfg.json)
==============================================================================

{
    "enabled": true,
    "prohibitedWords": [
        "badword",
        "badword2"
    ],
    "prohibitedWordsFile": "",
    "threshold": 3,
    "action": 0,
    "muteDuration": 5,
    "tempbanDuration": 3,
    "silentMode": false,
    "messagePrefix": "^5[AutoMod]^7: ",
    "privateMessage": "^1You have been flagged for using prohibited language. Further violations will result in punishment."
}

PARAMETERS:

enabled (bool):
  Master switch to enable/disable the plugin entirely
  Default: true

prohibitedWords (list of strings):
  List of words/phrases to detect in chat messages
  - Case-insensitive (matches "BadWord" and "badword")
  - Substring matching (matches "mybadwordhere")
  - Color codes stripped before matching
  - Can be defined directly in config OR loaded from external file (see prohibitedWordsFile)
  Default: ["badword", "spam", "offensive"]

prohibitedWordsFile (string):
  Path to external text file containing prohibited words (one per line)
  - If specified, this REPLACES the prohibitedWords array
  - Supports both absolute paths and paths relative to plugin directory
  - Lines starting with # are treated as comments and ignored
  - Empty lines are ignored
  - Example: "prohibitedWords.txt" or "/path/to/custom/words.txt"
  - Makes it easier to maintain large word lists
  Default: "" (empty, uses prohibitedWords array instead)

threshold (int):
  Number of violations before punishment is applied
  Must be at least 1
  Default: 3

action (int):
  Punishment type to apply when threshold is reached
  0 = Mute player for configurable duration (minutes)
  1 = Kick player from server
  2 = Tempban player for configurable duration (rounds)
  3 = Ban player's IP address (permanent)
  Default: 0

muteDuration (int):
  Duration in MINUTES to mute player (used with action 0)
  Default: 5

tempbanDuration (int):
  Duration in ROUNDS to tempban player (used with action 2)
  Default: 3

silentMode (bool):
  If true: No private messages sent to players, no public announcements
  If false: Send warnings to offenders via SvTell, announce punishments
  Default: false

messagePrefix (string):
  Prefix for server messages (supports MB2 color codes)
  Default: "^5[AutoMod]^7: "

privateMessage (string):
  Message sent to player when violation is detected (ignored if silentMode is true)
  Default: "^1You have been flagged for using prohibited language. Further violations will result in punishment."

==============================================================================
ACTION MODES
==============================================================================

Action 0: MUTE (DEFAULT)
- Mutes player for specified duration (muteDuration in minutes)
- Player cannot send chat messages
- Player can continue playing
- Suitable for first-time offenders or moderate violations

Action 1: KICK
- Immediately kicks player from server
- Player can rejoin immediately
- Suitable for disruptive behavior that needs immediate response

Action 2: TEMPBAN
- Temporarily bans player for specified rounds (tempbanDuration)
- Player cannot rejoin until tempban expires
- Suitable for repeat offenders or serious violations

Action 3: BAN (PERMANENT)
- Permanently bans player's IP address
- No duration - ban is permanent until manually removed
- Player cannot rejoin unless unbanned manually by admin
- Suitable for extreme violations or persistent offenders
- WARNING: Use with caution, this is irreversible without manual intervention

==============================================================================
WORD DETECTION BEHAVIOR
==============================================================================

SUBSTRING MATCHING:
The plugin uses substring matching, meaning "badword" will match:
- "badword" (exact match)
- "mybadwordhere" (contained in larger string)
- "badword123" (at start)
- "123badword" (at end)

CASE-INSENSITIVE:
- "BadWord", "BADWORD", "badword" all match "badword" in config

COLOR CODE STRIPPING:
- MB2 color codes (^0-^9) are stripped before matching
- "^1bad^7word" matches "badword" in config

MULTIPLE WORDS IN ONE MESSAGE:
- If a message contains multiple prohibited words, it counts as 1 violation total
- Example: "This is badword and spam" = 1 violation (not 2)

==============================================================================
VIOLATION TRACKING
==============================================================================

SESSION TRACKING (in-memory, resets on map change):
- Tracks violation count per IP address
- Tracks which violation counts triggered punishments
- Resets when map changes
- Resets when Godfinger restarts

PERSISTENT LOGGING (punishedPlayers.json):
- Permanently logs all violations
- Survives map changes and Godfinger restarts
- Tracks: IP, player name, message, matched words, timestamp, action taken
- Used for historical records and admin review

IP-BASED TRACKING:
- Players tracked by IP address, not name
- Name changes do not reset violation counter
- Multiple players on same IP share violation counter

==============================================================================
PUNISHMENT BEHAVIOR
==============================================================================

THRESHOLD SYSTEM:
1. Player violates chat rules (uses prohibited word)
2. Violation counter increments for their IP
3. Private warning sent (if not silent mode)
4. When counter reaches threshold, punishment is applied
5. Counter continues incrementing after punishment
6. Every time threshold is reached again, punishment re-applies

EXAMPLE (threshold=3, action=0 mute):
- Violation 1: Warning sent
- Violation 2: Warning sent
- Violation 3: MUTED (threshold reached)
- Violation 4: Warning sent
- Violation 5: Warning sent
- Violation 6: MUTED AGAIN (threshold reached again)

REPEATED PUNISHMENTS:
- Punishment re-applies every time threshold is reached
- With threshold=3: punished at 3, 6, 9, 12, etc.
- This prevents players from continuing toxic behavior after one punishment

==============================================================================
SMOD ADMIN COMMANDS
==============================================================================

!kickoffenders
  Description: Kicks all players who have violations in current session
  Permissions: SMOD only
  Usage: /smod smsay !kickoffenders
  Example: Kicks all players with violation count > 0

!tempbanoffenders <rounds>
  Description: Tempbans all offenders for specified number of rounds
  Permissions: SMOD only
  Usage: /smod smsay !tempbanoffenders <rounds>
  Example: !tempbanoffenders 5 (tempbans all offenders for 5 rounds)

!amstat | !automodstatus
  Description: Shows current automod statistics
  Permissions: SMOD only
  Usage: /smod smsay !amstat
  Output: Session offenders/violations + lifetime logged violations

!clearmodlog
  Description: Clears all violation history from punishedPlayers.json
  Permissions: SMOD only
  Usage: /smod smsay !clearmodlog
  Warning: This permanently deletes all logged violations. Use with caution.
  Output: Confirmation message with number of entries cleared

These commands will appear in the SMOD help menu when you type:
  /smod smsay !help

==============================================================================
SILENT MODE
==============================================================================

When silentMode is enabled (set to true):
- No private messages sent to detected players
- No public announcements when punishments are applied
- No map change reset announcements
- Plugin runs completely silently from player perspective
- All logging still occurs normally in Godfinger logs
- Best for: Stealth enforcement where you don't want players to know they're being monitored

When silentMode is disabled (set to false):
- Private message sent to player on each violation (via SvTell)
- Public announcement when punishment is applied
- Map change reset announced to all players
- Best for: Transparent moderation with clear warnings

==============================================================================
TROUBLESHOOTING
==============================================================================

PLUGIN NOT LOADING:
- Check godfingerCfg.json has correct plugin entry
- Check Godfinger logs for error messages
- Verify plugin files exist in plugins/shared/automod/

VIOLATIONS NOT DETECTED:
- Check "enabled": true in automodCfg.json
- Check prohibitedWords list is not empty
- Check player messages are being sent in chat (not private messages)
- Check Godfinger logs for "violated chat rules" messages

PUNISHMENTS NOT APPLYING:
- Check threshold is being reached (count >= threshold)
- Check action mode is valid (0-3)
- Check server interface has permission to execute commands
- Check Godfinger logs for "Error applying punishment" messages

FALSE POSITIVES:
- Avoid very short words (2-3 letters) due to substring matching
- Words like "grass", "class", "assassin" may contain prohibited substrings
- Test thoroughly before deploying to production
- Consider using more specific phrases instead of single words

SMOD COMMANDS NOT APPEARING IN !help:
- Check SERVER_DATA.SetServerVar("registeredSmodCommands") is called in OnInitialize
- Restart Godfinger to register commands
- Check no errors in logs during plugin initialization

==============================================================================
TECHNICAL DETAILS
==============================================================================

FILES:
- automod.py: Main plugin code
- automodCfg.json: Configuration (gitignored)
- punishedPlayers.json: Violation log (gitignored, auto-created)
- readme.txt: This documentation

EVENTS HANDLED:
- GODFINGER_EVENT_TYPE_MESSAGE: Chat message monitoring
- GODFINGER_EVENT_TYPE_MAPCHANGE: Session reset on map change
- GODFINGER_EVENT_TYPE_SMSAY: SMOD admin commands

DATA STORAGE:
- Session violations: In-memory dictionary, cleared on map change
- Violation log: JSON file, persists across restarts
- Configuration: JSON file, loaded on plugin start

PERFORMANCE:
- Minimal CPU usage (only processes chat messages)
- No continuous background tasks
- No database connections
- Violation log writes are asynchronous (non-blocking)

==============================================================================
CHANGELOG
==============================================================================

Version 1.0.0 (Initial Release):
- Chat message monitoring for prohibited words
- IP-based violation tracking
- Configurable punishment actions (mute, kick, tempban, ban)
- Session-based counters with map change reset
- Persistent violation logging
- SMOD commands: !kickoffenders, !tempbanoffenders, !amstat
- Silent mode for stealth enforcement
- Comprehensive error handling

==============================================================================
SUPPORT
==============================================================================

For issues, feature requests, or questions:
1. Check the troubleshooting section above
2. Review Godfinger logs for error messages
3. Verify configuration file syntax (valid JSON)
4. Test with minimal prohibited words list first

==============================================================================
