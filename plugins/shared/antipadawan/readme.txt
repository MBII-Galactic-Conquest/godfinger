=== Anti-Padawan Plugin for Godfinger ===
=== Authored by 2cwldys ===

DESCRIPTION:
The Anti-Padawan plugin detects players with blocked words in their name and takes configurable
actions ranging from marking them for teamkill to banning them. The plugin always sends a private
message to detected players asking them to change their username.

FEATURES:
- Name-based detection (case-insensitive, color code stripping, special character removal)
- Multiple word detection (supports list of blocked words)
- Strict or loose matching modes (configurable)
- 4 action modes (0-3) with different enforcement levels
- Always sends private message to detected players
- IP-based penalty tracking (automatically removes penalties when player changes to allowed name)
- Real-time name change detection via polling (detects name changes within 2 seconds)
- Automatic penalty removal when changing to allowed names
- Name change abuse detection (tempbans repeat offenders)
- Master enable/disable switch
- No database needed
- Self-contained (no external dependencies)

INSTALLATION:
1. Ensure the antipadawan plugin directory is in: plugins/shared/antipadawan/
2. Add the following to your godfinger.py configuration in the "Plugins" section:
   {
       "path": "plugins.shared.antipadawan.antipadawan"
   }
3. Start the server - the plugin will auto-create antipadawanCfg.json with defaults

CONFIGURATION (antipadawanCfg.json):

{
    "enabled": true,
    "action": 0,
    "strictMatch": true,
    "silentMode": false,
    "messagePrefix": "^1[Anti-Padawan]^7: ",
    "privateMessage": "^1Please change your username to play on this server.^7 Your username is blocked.",
    "marktkDuration": 60,
    "muteDuration": 10,
    "detectedWords": ["padawan", "noob"],
    "nameChangeAbuse": {
        "enabled": true,
        "maxChanges": 3,
        "timeWindow": 60,
        "tempbanRounds": 5
    }
}

PARAMETERS:
- "enabled" (bool): Master switch - set to false to disable plugin entirely
- "action" (int): Action mode (0-3), see ACTION MODES below
- "strictMatch" (bool): If true, name must be EXACTLY the blocked word. If false, blocked word can be part of name (default: true)
- "silentMode" (bool): If true, suppresses all private messages to players (default: false)
- "messagePrefix" (string): Prefix for server messages with MB2 color codes
- "privateMessage" (string): Private message sent via SvTell to detected players (ignored if silentMode is true)
- "marktkDuration" (int): Duration in minutes for MarkTK (actions 0 and 3)
- "muteDuration" (int): Duration in minutes for mute (action 3 only)
- "detectedWords" (list): List of words to detect in player names (supports legacy "detectedWord" string)
- "nameChangeAbuse" (object): Configuration for name change abuse detection and tempban
  - "enabled" (bool): Enable/disable name change abuse detection (default: true)
  - "maxChanges" (int): Number of changes to blocked names before tempban (default: 3)
  - "timeWindow" (int): Time window in seconds to count name changes (default: 60)
  - "tempbanRounds" (int): Number of rounds to tempban repeat offenders (default: 5)

ACTION MODES:

Action 0: MarkTK + Allow Play (DEFAULT)
- Marks player for teamkill immediately
- Sends private message
- Allows player to continue playing
- Uses marktkDuration setting
- Best for: Warning players without kicking them

Action 1: Kick Immediately
- Sends private message
- Kicks player from server immediately
- Player can reconnect with different name
- Best for: Strict enforcement without banning

Action 2: Ban IP + Kick
- Sends private message
- Bans player IP address
- Kicks player from server
- Permanently blocks the IP
- Best for: Strongest enforcement (use with caution)

Action 3: MarkTK + Mute + Allow Play
- Marks player for teamkill
- Mutes player for configured duration
- Sends private message
- Allows player to continue playing
- Uses both marktkDuration and muteDuration settings
- Best for: Penalizing without kicking while limiting communication

NAME DETECTION:
The plugin uses a robust name detection system:
1. Strips MB2 color codes (^0-^9)
2. Converts to lowercase for case-insensitive matching
3. Removes special characters (:|-|.|,|;|=|/|\||`|~|"|'|[|]|(|)|_)
4. Checks based on strictMatch setting:
   - strictMatch: false - Blocked word can be PART of the name (loose matching)
   - strictMatch: true (default) - Name must be EXACTLY the blocked word (after cleaning)
5. Supports legacy "detectedWord" (single string) for backwards compatibility

LOOSE MODE Examples (strictMatch: false, detectedWords: ["padawan", "noob"]):
- "^1Padawan^7" → DETECTED (exact match after cleaning)
- "PadawanKiller" → DETECTED (contains "padawan")
- "The_Padawan_123" → DETECTED (contains "padawan")
- "p.a.d.a.w.a.n" → DETECTED (special chars removed, becomes "padawan")
- "PADAWAN" → DETECTED (case-insensitive)
- "NoobPlayer" → DETECTED (contains "noob")
- "N00B" → DETECTED (matches "noob" after cleaning)
- "NormalPlayer" → NOT detected (no blocked words found)

STRICT MODE Examples (strictMatch: true, detectedWords: ["padawan", "noob"]):
- "^1Padawan^7" → DETECTED (exactly "padawan" after cleaning)
- "PadawanKiller" → NOT detected (name is "padawankiller", not exactly "padawan")
- "The_Padawan_123" → NOT detected (name is "thepadawan123", not exactly "padawan")
- "p.a.d.a.w.a.n" → DETECTED (special chars removed, becomes exactly "padawan")
- "PADAWAN" → DETECTED (case-insensitive exact match)
- "NoobPlayer" → NOT detected (name is "noobplayer", not exactly "noob")
- "N00B" → DETECTED (exactly "noob" after cleaning)
- "NormalPlayer" → NOT detected (no exact matches)

PRIVATE MESSAGING:
- Private message is ALWAYS sent to detected players regardless of action mode (unless silentMode is enabled)
- Uses SvTell (private message) so only the detected player sees it
- Message is configurable via privateMessage setting
- Encourages players to change their name to play normally
- Set silentMode to true to suppress all player messages and run silently

SILENT MODE:
When silentMode is enabled (set to true):
- No private messages are sent to detected players
- No "Thank you" messages are sent when penalties are removed
- Plugin runs completely silently, only executing RCON commands
- All logging still occurs normally in the Godfinger logs
- Best for: Stealth enforcement where you don't want players to know they're being tracked

REAL-TIME NAME CHANGE DETECTION:
The plugin monitors player name changes in real-time using a polling mechanism:
- Checks player names every 2 seconds via the 'status' command
- Detects name changes immediately (not dependent on spawn/team change events)
- Automatically applies penalties when player changes TO a blocked name
- Automatically removes penalties when player changes TO an allowed name
- Works on both Windows (PTY) and Linux (RCON) interfaces
- Only removes plugin-applied penalties (preserves admin-applied marks/mutes)

NAME CHANGE FLOW:
1. Player joins as "GoodName" → No penalties
2. Player changes to "Padawan" (in-game, 2 second detection)
   → Plugin detects change within 2 seconds
   → Applies MarkTK/Mute penalties (based on action mode)
   → Sends private message
   → Tracks as name change #1
3. Player changes to "GoodName2" (in-game, 2 second detection)
   → Plugin detects change within 2 seconds
   → Removes MarkTK/Mute penalties (if no admin marks)
   → Not counted as abuse (only changing TO blocked names counts)
4. Player changes to "Padawan" again
   → Applies penalties again
   → Tracks as name change #2
5. Player changes to "GoodName3"
   → Removes penalties
6. Player changes to "Padawan" third time
   → Tracked as name change #3
   → TEMPBANNED for 5 rounds (configurable)
   → Player is kicked and cannot rejoin for 5 rounds

NAME CHANGE ABUSE PREVENTION:
To prevent players from exploiting the system by repeatedly changing between blocked/allowed names:
- Plugin tracks how many times a player changes TO a blocked name
- Only changes TO blocked names are counted (changing to allowed names is not counted)
- Tracking is based on IP address and time window (default: 60 seconds)
- After maxChanges (default: 3) within timeWindow, player is tempbanned
- Tempban duration is configurable (default: 5 rounds)
- Server announces the tempban publicly
- Tempban uses MB2's built-in 'tempban' command (prevents rejoin for N rounds)

ABUSE DETECTION CONFIG:
{
    "nameChangeAbuse": {
        "enabled": true,           // Enable/disable abuse detection
        "maxChanges": 3,            // 3 changes to blocked names = tempban
        "timeWindow": 60,           // Count changes within 60 seconds
        "tempbanRounds": 5          // Tempban for 5 rounds
    }
}

ABUSE DETECTION EXAMPLES:
Example 1: Player changes 2 times within 60 seconds
  - "GoodName" → "Padawan" (change #1) → "GoodName" → "Padawan" (change #2)
  - Result: Penalties applied/removed, no tempban (under threshold)

Example 2: Player changes 3 times within 60 seconds
  - "GoodName" → "Padawan" (#1) → "GoodName" → "Padawan" (#2) → "GoodName" → "Padawan" (#3)
  - Result: TEMPBANNED for 5 rounds on the 3rd change

Example 3: Player changes slowly over 2 minutes
  - "GoodName" → "Padawan" (0:00, #1) → "GoodName" (0:30) → "Padawan" (1:30, #2)
  - At 1:30, the change from 0:00 is outside the 60s window (expired)
  - Only 1 recent change counted, no tempban

PENALTY TRACKING (Actions 0 and 3):
For actions that apply penalties but allow continued play (MarkTK or MarkTK+Mute):
- Plugin tracks penalized players by IP address in antipadawan_tracking.json
- Penalties are applied when:
  1. Player JOINS with a blocked name (OnClientConnect event)
  2. Player CHANGES to a blocked name while in-game (OnClientChanged event)
- Penalties are ONLY removed when player reconnects with an allowed name (OnClientBegin event)
  - Player must DISCONNECT and REJOIN with an allowed name to clear penalties
  - In-game name changes to allowed names do NOT remove penalties (prevents exploit)
  - MarkTK is cleared using unmarktk command
  - Mute is removed using unmute command
  - Player receives a "Thank you" message confirming penalties are cleared (unless silentMode is enabled)
- If they reconnect with a blocked name, penalties remain in effect
- Tracking file is automatically ignored by git (.gitignore includes *.json)
- No tracking is done for actions 1-2 (kick/ban) since player is removed from server

ANTI-ABUSE PROTECTION:
To prevent exploits that could clear legitimate admin-applied penalties:
- Plugin penalties can ONLY be removed by disconnecting and rejoining (not in-game name changes)
- The unmarktk/unmute commands clear ALL marks on a player, not just plugin-applied ones
- If we allowed in-game name changes to clear marks, players could exploit:
  Example exploit: Admin marks player → Player changes to "Padawan" → Plugin marks again →
  Player changes to "GoodName" → Plugin calls unmarktk → Admin's legitimate mark is cleared!
- By requiring disconnect/rejoin, players cannot exploit the system to clear admin marks
- Players changing TO blocked names in-game ARE still penalized (and must rejoin to clear)

ADMIN PENALTY PERSISTENCE:
- Admin penalties applied via !gfmarktk or !gfmute are tracked by player IP
- When a tracked player disconnects and rejoins (even with a different name):
  * The plugin automatically re-applies their admin penalties
  * Duration is preserved (e.g., if 45 min remain, re-applied for 45 min)
  * Logs show who originally applied the penalty
- This prevents players from escaping admin penalties by:
  * Changing their name
  * Rejoining the server
  * Switching to different aliases
- Admin penalties persist until:
  * They expire naturally after their duration
  * An admin manually removes them with !gfunmarktk or !gfunmute
  * The server/godfinger restarts (admin tracking is in-memory only)

ADMIN MARK TRACKING:
The plugin tracks admin-applied marks/mutes to prevent accidentally clearing them and to persist them across reconnects:
- Admin marks/mutes are tracked in-memory only (cleared on godfinger restart)
- Admins should use the special !gf commands to apply marks/mutes that the plugin tracks:
  * /smod smsay !gfmarktk <playername> <duration> - Mark player for TK and track it
  * /smod smsay !gfmute <playername> <duration> - Mute player and track it
  * /smod smsay !gfunmarktk <playername> - Unmark player and remove tracking
  * /smod smsay !gfunmute <playername> - Unmute player and remove tracking
  * /smod smsay !padawanips - Show all tracked plugin penalties (sent to smod chat)
  * /smod smsay !kickpadawans - Kick all players with blocked names

KEY FEATURES:
- Admin penalties PERSIST across reconnects: When a player with an admin mark/mute disconnects
  and rejoins (even with a different name), the plugin automatically re-applies the penalty
- Plugin will NOT clear penalties on players who have active admin-tracked marks/mutes
- Admin penalties automatically expire after their duration
- Players can change their name but admin penalties remain until expired or manually removed
- Use !gfunmarktk or !gfunmute to manually remove penalties and clear tracking

TECHNICAL DETAILS:
- In-memory tracking format: { "player_ip": { "marktk": {...}, "mute": {...} } }
- Each entry contains: { "expires": timestamp, "duration": minutes, "admin_name": str, "admin_ip": str }
- On player reconnect, plugin checks for active admin penalties and re-applies them
- This ensures legitimate admin marks are never cleared by the plugin's auto-unmark feature
- Admin tracking is cleared on godfinger/server restart (in-memory only, not persisted)

ADMIN COMMANDS:
All admin commands are executed via /smod smsay:

!gfmarktk <playername> <duration>
  - Marks the player for teamkilling for specified duration (in minutes)
  - Tracks the mark to prevent plugin from auto-clearing it
  - Example: /smod smsay !gfmarktk Padawan 60

!gfmute <playername> <duration>
  - Mutes the player for specified duration (in minutes)
  - Tracks the mute to prevent plugin from auto-clearing it
  - Example: /smod smsay !gfmute Padawan 30

!gfunmarktk <playername>
  - Removes TK mark from player and clears admin tracking
  - Example: /smod smsay !gfunmarktk Padawan

!gfunmute <playername>
  - Unmutes player and clears admin tracking
  - Example: /smod smsay !gfunmute Padawan

!padawanips
  - Shows all tracked plugin penalties (IPs with blocked names)
  - Sent to smod chat (visible to all admins)
  - Displays: IP address, last seen name, MarkedTK status, Muted status
  - Example: /smod smsay !padawanips

!kickpadawans
  - Kicks all players currently on the server with blocked names
  - Uses the strictMatch config setting to determine matching behavior
  - Publicly announces how many players were kicked and which mode was used
  - Example: /smod smsay !kickpadawans

EXAMPLES:

1. Default Setup (MarkTK Warning):
   {
       "enabled": true,
       "action": 0,
       "marktkDuration": 60,
       "detectedWord": "padawan"
   }
   Result: Players with "padawan" in name are marked for TK for 60 minutes, receive message, can play

2. Immediate Kick (Strict):
   {
       "enabled": true,
       "action": 1,
       "detectedWord": "padawan"
   }
   Result: Players with "padawan" in name are kicked immediately, can reconnect with different name

3. Ban and Kick (Strongest):
   {
       "enabled": true,
       "action": 2,
       "detectedWord": "padawan"
   }
   Result: Players with "padawan" in name are IP banned then kicked permanently

4. MarkTK + Mute (Penalty):
   {
       "enabled": true,
       "action": 3,
       "marktkDuration": 60,
       "muteDuration": 60,
       "detectedWord": "padawan"
   }
   Result: Players with "padawan" are marked for TK (60 min), muted (60 min), receive message, can play

5. Multiple Word Detection (Loose Mode):
   {
       "enabled": true,
       "action": 1,
       "strictMatch": false,
       "detectedWords": ["padawan", "noob"]
   }
   Result: Detects words as part of name - blocks "Padawan", "PadawanKiller", "NoobPlayer", etc.

6. Strict Mode (Exact Match Only - Default):
   {
       "enabled": true,
       "action": 1,
       "strictMatch": true,
       "detectedWords": ["padawan", "noob"]
   }
   Result: Only blocks if name is EXACTLY "padawan" or "noob" - allows "PadawanKiller", "NoobSlayer", etc.

7. Custom Single Word (Legacy Support):
   {
       "enabled": true,
       "action": 1,
       "detectedWord": "padawan"
   }
   Result: Still supports legacy "detectedWord" (string) format for backwards compatibility

ADMIN COMMAND SCENARIOS:

Scenario A: Griefer with good name
   1. Player "Griefer" team kills repeatedly
   2. Admin: /smod smsay !gfmarktk Griefer 60
   3. Player marked for 60 minutes + tracked in admin tracking
   4. Player leaves and rejoins as "NewName"
   5. Plugin re-applies mark for remaining duration
   6. Player still marked even with different name!
   7. After 60 minutes, mark expires and tracking is cleared

Scenario B: Mixed plugin + admin penalties
   1. Player joins as "Padawan" → Plugin applies marktk/mute (action 3)
   2. Admin sees griefing behavior: /smod smsay !gfmarktk Padawan 30
   3. Player now has BOTH plugin penalty + admin penalty
   4. Player leaves and rejoins as "GoodName"
   5. Plugin removes plugin penalties (name is now allowed)
   6. Plugin re-applies admin mark (30 min remaining)
   7. Result: Plugin penalties cleared, admin mark persists!

Scenario C: Admin removes penalty early
   1. Admin: /smod smsay !gfmarktk Griefer 60
   2. Player marked + tracked
   3. Player apologizes and behaves
   4. Admin: /smod smsay !gfunmarktk Griefer
   5. Mark removed + admin tracking cleared
   6. Player rejoins → No penalties applied

Scenario D: Checking tracked IPs
   1. Admin: /smod smsay !padawanips
   2. Shows all IPs with plugin penalties (blocked names)
   3. Displays IP, last name, marktk status, mute status
   4. Sent to smod chat (visible to all admins)

Scenario E: Mass kick blocked names
   1. Multiple players join with "Padawan", "Padawan[1]", etc.
   2. Admin: /smod smsay !kickpadawans
   3. All players with blocked names kicked
   4. Public announcement shows count and strict/loose mode

LOGGING:
The plugin logs to the Godfinger log file with these levels:
- DEBUG: Name detection matches, private messages sent
- INFO: Players detected on startup/connect, actions taken (kick/ban/marktk/mute)
- ERROR: Configuration errors, name checking errors, message sending errors

TROUBLESHOOTING:

Players being detected incorrectly?
  * Check detectedWord spelling in config
  * Remember: detection is case-insensitive and strips special characters
  * Enable debug logging to see exact match results
  * Verify color codes are being stripped (^0-^9 format)

Plugin not loading?
  * Check godfinger.py plugin configuration
  * Verify path: "plugins.shared.antipadawan.antipadawan"
  * Check log files for initialization errors
  * Ensure no syntax errors in antipadawanCfg.json

Config not saving or loading?
  * Ensure antipadawanCfg.json has valid JSON syntax
  * Check file permissions in plugin directory
  * Plugin auto-creates config with defaults if missing
  * Restart server after config changes

Players not receiving private messages?
  * Verify SvTell is working (test with other commands)
  * Check that privateMessage is not empty in config
  * Review logs for message sending errors
  * Ensure player client ID is valid

TECHNICAL DETAILS:
- Event handling: CLIENTCONNECT (detection and penalty removal)
- Returns False from event handlers to allow other plugins to process events
- Uses Python standard library only (logging, re, os, json, time)
- No database or external API calls
- IP-based tracking stored in antipadawan_tracking.json (auto-created, git-ignored)
- Penalty removal: UnmarkTK command for TK removal, ClientUnmute for mute removal
- Color code handling uses MB2 standard (^0-^9)
- Name detection pattern adapted from RTV plugin's protected names

NOTES:
- Plugin checks both existing players on startup and new connections
- Action mode affects behavior but private message is ALWAYS sent
- Special character removal helps catch obfuscated names
- MarkTK duration is in minutes (not seconds)
- Mute duration is in minutes (not seconds)
- Plugin works with both RCON and PTY interface modes
- Tracking file (antipadawan_tracking.json) is automatically created and managed
- Penalties are automatically removed when player changes to an allowed name
- Tracking is IP-based, so changing IP will bypass tracking (but they'd still get re-penalized if using blocked name)

COMPATIBILITY:
- Requires Godfinger Movie Battles II plugin system
- Tested with MB2 server
- No conflicts with other plugins (returns False from event handlers)
- Compatible with whitelist, vpnmonitor, and other access control plugins