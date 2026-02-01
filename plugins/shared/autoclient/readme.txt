================================================================================
                            AUTOCLIENT PLUGIN
                           Authored by 2cwldys
================================================================================

OVERVIEW
--------
The AutoClient plugin automatically spawns fake game clients to make your server
appear populated. As real players join, fake clients are removed to make room.
This helps attract players to servers that would otherwise appear empty.

** WINDOWS ONLY ** - This plugin only works on Windows systems.


** DISCLAIMER **
----------------
USE THIS PLUGIN AT YOUR OWN RISK. The authors and maintainers of this plugin
are not responsible for any violation of master server Terms of Service, server
delistment, bans, or any other consequences that may arise from using fake
clients to artificially inflate server population. By using this plugin, you
acknowledge that you understand and accept these risks.


REQUIREMENTS
------------
1. Windows operating system
2. MBII game client (mbii.x86.exe) accessible on the same machine
3. Dedicated server (mbiided.x86.exe) must be running
4. g_anticheat must be set to 0 (plugin sets this automatically)


** IMPORTANT: ANTI-CHEAT SETTING **
-----------------------------------
This plugin REQUIRES g_anticheat to be set to 0 on your server. If g_anticheat
is set to 0, the fake clients will be kicked immediately upon connecting.

The plugin automatically sets "g_anticheat 0" when it starts. However, if you
have this setting configured elsewhere (server.cfg, command line, etc.) make
sure it is set to 0, not 1.

If fake clients keep getting kicked immediately, check your server configuration
for any setting that might be overriding g_anticheat back to 1.

** IMPORTANT: TOGGLE AUTOCLIENT.CFG **
-----------------------------------
Change the value from 0 to 1, in godfinger/start/autoclient.cfg, in order for
this plugin to function properly, and as anticipated.


HOW IT WORKS
------------
1. When the server starts (and is empty), the plugin spawns fake clients up to
   the configured maximum
2. Fake clients connect from localhost (127.0.0.1)
3. When a real player joins (detected by non-localhost IP), one fake client is
   terminated to make room
4. When real players leave, fake clients can be respawned to maintain population
5. All fake client processes are terminated when the plugin shuts down


CONFIGURATION
-------------
Configuration is stored in autoclientCfg.json (auto-created on first run):

{
    "enabled": true,
    "maxFakeClients": 4,
    "clientExecutablePath": "C:/Path/To/GameData/mbii.x86.exe",
    "serverIP": "127.0.0.1",
    "serverPort": "29070",
    "serverProcessName": "mbiided.x86.exe",
    "launchDelay": 5.0,
    "healthCheckInterval": 30.0,
    "nameList": ["Trooper", "Soldier", "Recruit", "Stormtrooper", "Rebel", "Cadet", "Scout", "Apprentice", "Padawan", "Initiate", "Cultist", "Rosh", "Kyle Katarn", "Tavion", "Alora", "Luke Skywalker", "Jerec", "Desann", "Master", "Guardian"],
    "randomNamePrefix": "Guest_",
    "messagePrefix": "^3[AutoClient]^7: "
}

PARAMETERS:

  enabled               - Master switch to enable/disable the plugin

  maxFakeClients        - Maximum number of fake clients to maintain when server
                          is empty. As real players join, this target decreases.

  clientExecutablePath  - Full path to mbii.x86.exe game client
                          Use forward slashes (/) or escaped backslashes (\\)

  serverIP              - IP address for clients to connect to
                          Usually "127.0.0.1" for local server

  serverPort            - Server port (default: "29070")

  serverProcessName     - Name of the dedicated server process to check
                          (default: "mbiided.x86.exe")
                          Plugin will not spawn clients unless this is running

  launchDelay           - Seconds to wait between spawning each client
                          Prevents overwhelming the server with connections

  healthCheckInterval   - Seconds between process health checks
                          Dead clients are detected and re-tracked

  nameList              - List of names to assign to fake clients
                          Names are used in order, then cycle back

  randomNamePrefix      - If nameList is exhausted, random names are generated
                          with this prefix (e.g., "Guest_A7X2")

  messagePrefix         - Prefix for admin notification messages


SMOD COMMANDS
-------------
All commands require SMOD privileges:

  !autoclient           - Show current status (fake/real client counts)
  !acs                  - Alias for !autoclient

  !toggleautoclient     - Enable/disable the plugin
  !tac                  - Alias for !toggleautoclient

  !spawnfake [count]    - Manually spawn fake client(s)
                          count defaults to 1 if not specified

  !killfakes            - Immediately terminate all fake clients


DETECTION METHOD
----------------
The plugin distinguishes real players from fake clients by IP address:

  - Fake clients connect from 127.0.0.1 (localhost)
  - Real players connect from external IP addresses

This means the plugin works correctly even if real players happen to have
similar names to fake clients.


PROCESS MANAGEMENT
------------------
Each fake client runs as a separate Windows process:
  - Spawned using subprocess with CREATE_NEW_CONSOLE flag
  - Each client gets its own console window
  - Terminated using process.terminate() when removed
  - All processes cleaned up on plugin shutdown

The plugin checks that mbiided.x86.exe is running before spawning any clients.
If the server process is not detected, clients will not be spawned.


STANDALONE TEST SCRIPT
----------------------
A standalone test script (spawnClient.py) is included for testing client
spawning without Godfinger:

Usage:
  python spawnClient.py --exe "C:/Path/To/mbii.x86.exe" --ip "127.0.0.1" --count 3

Arguments:
  --exe PATH        Path to mbii.x86.exe (required)
  --ip IP           Server IP to connect to (required)
  --port PORT       Server port (default: 29070)
  --count N         Number of clients to spawn (default: 1)
  --names LIST      Comma-separated names (e.g., "Bot1,Bot2,Bot3")
  --delay SECONDS   Delay between spawns (default: 3.0)
  --prefix TEXT     Prefix for random names (default: "Guest_")

Press Ctrl+C to terminate all spawned clients.


TROUBLESHOOTING
---------------
Q: Plugin says "Windows only" and doesn't activate
A: This plugin only works on Windows. It cannot run on Linux/Mac.

Q: Clients aren't spawning
A: Check:
   1. clientExecutablePath points to a valid mbii.x86.exe
   2. mbiided.x86.exe server process is running
   3. enabled is set to true in config
   4. maxFakeClients is greater than 0

Q: Clients spawn but immediately disconnect
A: The game server may be rejecting connections. Check:
   1. Server isn't full
   2. Server IP/port are correct
   3. No firewall blocking localhost connections

Q: Real players aren't being detected
A: The plugin uses IP-based detection. If players are connecting through
   localhost (127.0.0.1), they'll be detected as fake clients.

Q: Processes remain after shutdown
A: The plugin attempts to terminate all processes on shutdown. If some
   remain, you can manually kill them via Task Manager or use !killfakes.


RESOURCE CONSIDERATIONS
-----------------------
Each fake client is a full game process that consumes:
  - CPU cycles for rendering/game logic
  - Memory (varies by system, typically 200-500MB per client)
  - Network bandwidth (minimal for idle clients)

Recommended maximum fake clients based on system resources:
  - Light systems: 2-4 clients
  - Medium systems: 4-8 clients
  - High-end systems: 8-12 clients

Monitor system resources when first configuring maxFakeClients.


FILE STRUCTURE
--------------
plugins/shared/autoclient/
  ├── autoclient.py       - Main plugin file
  ├── autoclientCfg.json  - Configuration (auto-created)
  └── readme.txt          - This file


VERSION HISTORY
---------------
1.0.0 - Initial release
      - Windows-only fake client spawning
      - IP-based real/fake player detection
      - Auto-scaling based on real player count
      - SMOD commands for manual control
      - Server process check before spawning

================================================================================
