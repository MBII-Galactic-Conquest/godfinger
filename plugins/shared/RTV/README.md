# Godfinger RTV/RTM Plugin Configuration Guide

*Godfinger Plugin Engine created by 2cwldys, ACHUTA / Mantlar, and ViceDice*

*RTV Plugin Created by ACHUTA / Mantlar*

This document explains the configuration options for the RTV/RTM plugin for the Godfinger Movie Battles II scripting engine. The configuration file is in JSON format and allows you to customize various aspects of the plugin's behavior.

## General Settings

### `MBIIPath`
- **Description**: Path to your Movie Battles II installation directory.
- **Example (Windows)**: `"C:\\Program Files (x86)\\Steam\\steamapps\\common\\Jedi Academy\\GameData\\MBII\\"`
- **Example (Linux)**: `"/home/container/.local/share/openjk/MBII/"`
- **Notes**: This should point to the directory containing your MBII files.

### `pluginThemeColor`
- **Description**: Color used for plugin messages and highlights.
- **Possible Values**: Any valid color code found in `lib/shared/colors.py` (e.g., "red", "green", "blue", "lblue", etc.).
- **Example**: `"lblue"`

### `MessagePrefix`
- **Description**: Prefix used for plugin messages.
- **Example**: `"[RTV]^7: "`
- **Notes**: The plugin theme color's corresponding color code is added to the beginning of the message prefix. If this is not desirable, make sure the message prefix begins with a color code (^[0-9]) You can use color codes in the prefix (e.g., `^7` for white).

### `RTVPrefix`
- **Description**: Command prefix for RTV/RTM commands.
- **Example**: `"!"`
- **Notes**: Set to `false` to disable prefix requirements.

### `requirePrefix`
- **Description**: Whether commands must include the prefix to be recognized.
- **Possible Values**: `true` or `false`
- **Example**: `false`

### `kickProtectedNames`
- **Description**: Whether to kick players with protected names (e.g., "admin", "server").
- **Possible Values**: `true` or `false`
- **Example**: `true`

### `useSayOnly`
- **Description**: Whether to use `say` instead of `svsay` for messages.
- **Possible Values**: `true` or `false`
- **Example**: `false`

### `floodProtection`
- **Description**: Configuration for flood protection.
  - `enabled`: Whether flood protection is enabled.
  - `seconds`: Time window in seconds for flood protection checks.
  - **Example**:
    ```json
    "floodProtection" : {
        "enabled" : false,
        "seconds" : 0
    }
    ```

## RTV (Rock the Vote) Configuration

### Core Settings
- `enabled`: Whether RTV is enabled.
- `voteTime`: Time in seconds for the vote to last.
- `voteAnnounceTimer`: How often to announce vote progress in seconds.
- `voteRequiredRatio`: Minimum ratio of players needed to start a vote.
- `automaticMaps`: Whether to automatically include all maps or use custom lists.
- `primaryMaps` and `secondaryMaps`: Lists of maps to use for voting.
- `useSecondaryMaps`: Whether to include secondary maps in voting (0 = none, 1 = some, 2 = all).
- `mapBanList`: List of maps that cannot be nominated or voted for.

### Advanced Settings
- `mapTypePriority`: Configure priority for different map types.
  - `enabled`: Whether to use priority system.
  - `primary`: Priority value for primary maps.
  - `secondary`: Priority value for secondary maps.
  - `nochange`: Priority value for "Don't Change" option.
- `allowNominateCurrentMap`: Whether players can nominate the current map.
- `emptyServerMap`: Map to switch to when the server is empty.
- `timeLimit` and `roundLimit`: Configure time or round-based limits for map changes.
- `minimumVoteRatio`: Minimum participation ratio required for a valid vote.
- `successTimeout` and `failureTimeout`: Cooldown periods after successful or failed votes.
- `disableRecentlyPlayedMaps`: Time in seconds to avoid repeating recently played maps.
- `skipVoting`: Whether to skip voting once majority is reached.
- `secondTurnVoting`: Whether to allow second-round voting in case of ties.
- `changeImmediately`: Whether to change maps immediately when a vote passes.

## RTM (Rock the Mode) Configuration

### Core Settings
- `enabled`: Whether RTM is enabled.
- `voteTime`: Time in seconds for the vote to last.
- `voteAnnounceTimer`: How often to announce vote progress in seconds.
- `voteRequiredRatio`: Minimum ratio of players needed to start a vote.
- `modes_enabled`: List of game modes available for voting.
- `emptyServerMode`: Mode to switch to when the server is empty.

### Advanced Settings
- `timeLimit` and `roundLimit`: Configure time or round-based automatic RTV votes.
- `minimumVoteRatio`: Minimum participation ratio required for a valid vote.
- `successTimeout` and `failureTimeout`: Cooldown periods after successful or failed votes.
- `skipVoting`: Whether to skip voting once majority is reached.
- `secondTurnVoting`: Whether to allow second-round voting in case of ties.
- `changeImmediately`: Whether to change modes immediately when a vote passes.

## How to Use the Plugin

1. **Commands**:
   - `!rtv` or `!rockthevote`: Start an RTV vote.
   - `!rtm` or `!rockthemode`: Start an RTM vote.
   - `!nominate <map>`: Nominate a map for the next RTV vote.
   - `!maplist <#>`: Display the server's map list (paginated).
   - `!search <query>`: Search for maps by name.
   - `!help`: Display help for commands.

2. **Voting**:
   - Players can vote using numbers (1-6) during active votes.
   - Votes can be announced periodically during the voting window.

3. **Nominations**:
   - Players can nominate maps using `!nominate <map>`.
   - Nominated maps will appear in the next RTV vote.

## Notes

- Some settings require the server to be restarted to take effect.
- The `mapBanList` is case-insensitive and matches map file names.
- The `primaryMaps` and `secondaryMaps` lists are case-insensitive.
- You can customize the appearance of messages using color codes.

## Troubleshooting

- If the plugin is not working, check the `MBIIPath` setting.
- If maps are not being detected, ensure the plugin has access to the MBII directory.
- Check server logs for error messages related to the plugin.

## Feedback

If you have suggestions or need help with the configuration, feel free to reach out to the plugin author or create an issue on the Godfinger GitHub repository (https://github.com/MBII-Galactic-Conquest/godfinger/).