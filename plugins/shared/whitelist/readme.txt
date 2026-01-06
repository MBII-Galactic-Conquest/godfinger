=== Whitelist Plugin for Godfinger ===
=== Authored by 2cwldys ===

DESCRIPTION:
The whitelist plugin allows you to restrict server access to only approved players based on
their IP address and/or player alias (name). Any player not on the whitelist will be blocked
from joining the server.

FEATURES:
- IP-based whitelisting (supports single IPs and IP ranges)
- Alias-based whitelisting (supports player names with color code stripping)
- Configurable match logic (separate or both)
- Configurable block actions (kick only or ban + kick)
- Server broadcast messages when blocking players
- Master enable/disable switch
- SMOD commands for real-time whitelist management (!whitelist, !blacklist)

INSTALLATION:
1. Ensure the whitelist plugin directory is in: plugins/shared/whitelist/
2. Add the following to your godfinger.py configuration in the "Plugins" section:
   {
       "path": "plugins.shared.whitelist.whitelist"
   }
3. Start the server - the plugin will auto-create whitelistCfg.json with defaults

CONFIGURATION (whitelistCfg.json):

{
    "enabled": true,                    // Master switch - set to false to disable plugin
    "matchMode": "separate",            // Options: "separate", "both"
    "action": 0,                        // 0 = kick only, 1 = ban IP then kick
    "svsayOnAction": true,              // Broadcast block messages to server
    "messagePrefix": "^1[Whitelist]^7: ", // Message prefix with MB2 color codes
    "ipWhitelist": [                    // List of whitelisted IPs
        "127.0.0.1",                    // Single IP
        ["192.168.1.1", "192.168.1.255"] // IP range [start, end]
    ],
    "aliasWhitelist": [                 // List of whitelisted player names
        "AdminName",                    // Case-insensitive, color codes stripped
        "TrustedPlayer"
    ]
}

MATCH MODES:
- "separate" (default): Player passes if their IP OR alias matches the whitelist (most permissive)
- "both": Player must have both IP AND alias on whitelist (most restrictive)

ACTIONS:
- 0 (default): Kick only - removes player but allows reconnection with different IP/name
- 1: Ban IP then kick - permanently bans the IP address

IP WHITELIST FORMAT:
- Single IP: "192.168.1.100"
- IP range: ["192.168.1.1", "192.168.1.255"]
- Supports both IPv4 and IPv6

ALIAS MATCHING:
- Case-insensitive (e.g., "PlayerName" matches "playername")
- Automatically strips MB2 color codes (^0-^9)
- Example: "^1Admin^7Name" matches "AdminName"

SMOD COMMANDS:
Admins with SMOD privileges can manage the whitelist in real-time using chat commands:

!whitelist <IP or PlayerName> (alias: !wl)
  - Add an IP address to the whitelist
  - Examples:
    /smod smsay !whitelist 192.168.1.100
    /smod smsay !whitelist PlayerName
    /smod smsay !wl 10.0.0.50

!blacklist <IP or PlayerName> (alias: !bl)
  - Remove an IP address from the whitelist
  - Examples:
    /smod smsay !blacklist 192.168.1.100
    /smod smsay !blacklist PlayerName
    /smod smsay !bl 10.0.0.50

Notes on SMOD commands:
- If you specify a player name, the plugin will look up their current IP address
- Player name matching is case-insensitive and strips color codes
- Changes are immediately saved to whitelistCfg.json
- Feedback is sent to SMOD chat (SmSay)

EXAMPLES:

1. IP-Only Whitelist (Office Network):
   {
       "enabled": true,
       "matchMode": "separate",
       "ipWhitelist": [["192.168.1.1", "192.168.1.255"]],
       "aliasWhitelist": []
   }

2. Alias-Only Whitelist (Known Players):
   {
       "enabled": true,
       "matchMode": "separate",
       "ipWhitelist": [],
       "aliasWhitelist": ["Admin", "Moderator", "TrustedPlayer"]
   }

3. Strict Mode (Both Required):
   {
       "enabled": true,
       "matchMode": "both",
       "action": 1,
       "ipWhitelist": ["192.168.1.100"],
       "aliasWhitelist": ["ServerAdmin"]
   }

4. Mixed Mode (Multiple Options):
   {
       "enabled": true,
       "matchMode": "separate",
       "ipWhitelist": ["127.0.0.1", ["10.0.0.1", "10.0.0.10"]],
       "aliasWhitelist": ["Admin", "Moderator"]
   }

LOGGING:
The plugin logs to the Godfinger log file with these levels:
- DEBUG: Whitelist matches, detailed processing
- INFO: Player blocks
- ERROR: Configuration errors, IP parsing errors

TROUBLESHOOTING:
- Players being blocked incorrectly?
  * Check IP format in config
  * Verify alias spelling (remember color codes are stripped)
  * Check matchMode setting
  * Enable debug logging to see match results

- Plugin not loading?
  * Check godfinger.py plugin configuration
  * Verify path: "plugins.shared.whitelist.whitelist"
  * Check log files for errors

- Config not saving?
  * Ensure whitelistCfg.json has valid JSON syntax
  * Check file permissions

NOTES:
- No external dependencies required (uses Python standard library)
- No database needed (all config from JSON)
- Plugin checks both existing players on startup and new connections
- Returns False from event handler to allow other plugins to process events
- Color code format follows MB2 standard (^0-^9)
