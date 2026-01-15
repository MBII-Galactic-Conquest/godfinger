==============================================================================
BOUNCER PLUGIN FOR GODFINGER
Authored by 2cwldys and Hera
==============================================================================

DESCRIPTION:
Bouncer is an IP gate plugin that tracks all IP addresses joining the server.
Players with known IPs (previously seen) pass through without punishment.
New/unknown IPs receive configurable punishments (marktk, mute, or both).

This plugin is designed to deter trolls, griefers, and bad actors who create
new accounts to evade bans or cause trouble on the server.

FEATURES:
- IP-based player tracking with persistent storage
- Automatic detection of new vs. returning players
- Configurable punishments for first-time visitors (marktk, mute, or both)
- Alias tracking (stores first and most recent player names per IP)
- Timestamp tracking (first seen and last seen dates)
- Antipadawan integration (avoids duplicate punishments)
- SMOD admin command to clear the IP whitelist
- Silent mode for stealth enforcement
- Automatic config creation with sensible defaults

==============================================================================
INSTALLATION
==============================================================================

1. Ensure the bouncer plugin directory is in: plugins/shared/bouncer/

2. Add the plugin to your godfingerCfg.json in the "Plugins" array:
   {
       "path": "plugins.shared.bouncer.bouncer"
   }

3. Configure the plugin by editing plugins/shared/bouncer/bouncerCfg.json
   (auto-created with defaults on first run)

4. Restart Godfinger

==============================================================================
CONFIGURATION (bouncerCfg.json)
==============================================================================

{
    "enabled": true,
    "action": 0,
    "marktkDuration": 60,
    "muteDuration": 15,
    "silentMode": false,
    "messagePrefix": "^3[Bouncer]^7: ",
    "privateMessage": "Welcome to the server!"
}

PARAMETERS:

enabled (bool):
  Master switch to enable/disable the plugin entirely
  Default: true

action (int):
  Punishment type to apply to NEW IPs (first-time visitors)
  0 = MarkTK only (mark player for team killing penalty)
  1 = Mute only (player cannot send chat messages)
  2 = MarkTK AND Mute (both punishments applied)
  Default: 0

marktkDuration (int):
  Duration in MINUTES to mark player for TK (used with action 0 and 2)
  Default: 60

muteDuration (int):
  Duration in MINUTES to mute player (used with action 1 and 2)
  Default: 15

silentMode (bool):
  If true: No private messages sent to new players
  If false: Send welcome/warning message to new players via SvTell
  Default: false

messagePrefix (string):
  Prefix for server messages (supports MB2 color codes)
  Default: "^3[Bouncer]^7: "

privateMessage (string):
  Message sent to new players when they first join (ignored if silentMode is true)
  Default: "Welcome to the server!"

==============================================================================
ACTION MODES
==============================================================================

Action 0: MARKTK ONLY (DEFAULT)
- Marks new player for team killing penalty
- Player receives TK penalty points for any team damage
- Configured duration in marktkDuration (default 60 minutes)
- Player can still chat and play normally
- Suitable for: Deterring potential griefers without being too harsh

Action 1: MUTE ONLY
- Mutes new player for specified duration
- Player cannot send chat messages
- Configured duration in muteDuration (default 15 minutes)
- Player can still play normally
- Suitable for: Preventing chat spam from new accounts

Action 2: MARKTK AND MUTE
- Applies BOTH marktk and mute punishments
- Player is marked for TK AND cannot chat
- Uses both marktkDuration and muteDuration settings
- Suitable for: Maximum protection against new account abuse

==============================================================================
HOW IT WORKS
==============================================================================

WHEN A PLAYER CONNECTS:

1. Plugin detects player connection (CLIENT_BEGIN event)
2. Checks if player's IP exists in ipList.json

IF IP IS KNOWN (returning player):
- Updates their lastAlias to current name
- Updates lastSeen timestamp
- NO punishment applied
- Player joins normally

IF IP IS NEW (first-time visitor):
- Adds IP to ipList.json with alias and timestamp
- Checks if antipadawan would handle this player (name match)
- If antipadawan handles: Skip bouncer punishment (avoid duplicates)
- If not: Apply configured punishment (marktk/mute/both)
- Send private message (if not silent mode)

==============================================================================
DATA STORAGE (ipList.json)
==============================================================================

The plugin stores IP data in the following format:

{
    "192.168.1.100": {
        "firstAlias": "PlayerName",
        "lastAlias": "CurrentName",
        "firstSeen": "2025-01-15T12:00:00",
        "lastSeen": "2025-01-15T14:30:00"
    }
}

FIELDS:
- firstAlias: The player name used when they FIRST joined the server
- lastAlias: The player name used on their MOST RECENT connection
- firstSeen: ISO timestamp of their first connection
- lastSeen: ISO timestamp of their most recent connection

This data persists across:
- Map changes
- Godfinger restarts
- Server restarts

==============================================================================
ANTIPADAWAN INTEGRATION
==============================================================================

Bouncer automatically integrates with the antipadawan plugin to avoid
applying duplicate punishments to players.

HOW IT WORKS:
1. On startup, bouncer checks if antipadawan config exists
2. If found and enabled, bouncer loads antipadawan's detectedWords list
3. When a new IP joins, bouncer checks if their name would trigger antipadawan
4. If yes: Bouncer skips its punishment, lets antipadawan handle it
5. If no: Bouncer applies its configured punishment normally

This prevents situations where a new player with "Padawan" in their name
would receive BOTH antipadawan's marktk/mute AND bouncer's marktk/mute.

The integration uses the same name matching logic as antipadawan:
- Color code stripping
- Special character removal
- Strict/loose match modes (based on antipadawan config)

NOTE: The IP is still added to bouncer's database even if antipadawan handles
the punishment. This ensures they won't be punished by bouncer on future visits.

==============================================================================
SMOD ADMIN COMMANDS
==============================================================================

!cleargateips
  Description: Clears ALL IPs from the bouncer database (ipList.json)
  Permissions: SMOD only
  Usage: /smod smsay !cleargateips
  Effect: All players will be treated as new visitors on their next connection
  Warning: Use with caution - this removes all IP history

This command will appear in the SMOD help menu when you type:
  /smod smsay !help

==============================================================================
SILENT MODE
==============================================================================

When silentMode is enabled (set to true):
- No private messages sent to new players
- Punishments still apply silently
- All logging still occurs normally in Godfinger logs
- Best for: Stealth enforcement where you don't want players to know

When silentMode is disabled (set to false):
- Private message sent to new players when punishment is applied
- Best for: Transparent enforcement with clear communication

==============================================================================
USE CASES
==============================================================================

SCENARIO 1: Anti-Griefer Protection
  Config: action=0, marktkDuration=60
  Effect: New players get marked for TK for 1 hour
  Result: If they grief, they get TK penalties immediately

SCENARIO 2: Chat Spam Prevention
  Config: action=1, muteDuration=30
  Effect: New players are muted for 30 minutes
  Result: New accounts can't spam chat immediately

SCENARIO 3: Maximum Protection
  Config: action=2, marktkDuration=120, muteDuration=60
  Effect: New players are marked for TK (2hr) and muted (1hr)
  Result: New trolls have limited ability to cause damage

SCENARIO 4: Stealth Mode
  Config: action=2, silentMode=true
  Effect: Punishments applied without any notification
  Result: Trolls don't know they're being restricted

==============================================================================
TROUBLESHOOTING
==============================================================================

PLUGIN NOT LOADING:
- Check godfingerCfg.json has correct plugin entry
- Check Godfinger logs for error messages
- Verify plugin files exist in plugins/shared/bouncer/

NEW PLAYERS NOT BEING PUNISHED:
- Check "enabled": true in bouncerCfg.json
- Check player IP is not already in ipList.json
- Check Godfinger logs for "New IP detected" messages
- Verify action value is valid (0, 1, or 2)

RETURNING PLAYERS BEING PUNISHED:
- This should not happen if plugin is working correctly
- Check ipList.json contains their IP
- Check for Godfinger errors in logs

DUPLICATE PUNISHMENTS WITH ANTIPADAWAN:
- Bouncer should automatically skip if antipadawan handles the player
- Verify antipadawan config file exists and is enabled
- Check Godfinger logs for "antipadawan will handle" messages

SMOD COMMAND NOT APPEARING IN !help:
- Restart Godfinger to register commands
- Check no errors in logs during plugin initialization

==============================================================================
TECHNICAL DETAILS
==============================================================================

FILES:
- bouncer.py: Main plugin code
- bouncerCfg.json: Configuration (auto-created, gitignored)
- ipList.json: IP database (auto-created, gitignored)
- readme.txt: This documentation

EVENTS HANDLED:
- GODFINGER_EVENT_TYPE_CLIENT_BEGIN: Player makes it into the game
- GODFINGER_EVENT_TYPE_SMSAY: SMOD admin commands

DATA STORAGE:
- IP list: JSON file, persists across restarts
- Configuration: JSON file, loaded on plugin start

PERFORMANCE:
- Minimal CPU usage (only processes player connections)
- No continuous background tasks
- No database connections
- IP list writes occur on each new/returning player

==============================================================================
COMPATIBILITY
==============================================================================

This plugin is designed to work alongside:
- Antipadawan plugin (automatic integration, avoids duplicate punishments)
- Automod plugin (no conflicts, different event handling)
- Other Godfinger plugins (no shared resources)

==============================================================================
