import os
import sys
import json
import time
from datetime import datetime
import logging

import godfingerEvent
import lib.shared.client as client
import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import lib.shared.teams as teams

SERVER_DATA = None
PluginInstance = None
Log = logging.getLogger(__name__)


class AutomodPlugin:
    def __init__(self, serverData: serverdata.ServerData):
        self._serverData = serverData
        self._status = 0

        # Load configuration
        self.config = self._LoadConfig()
        self._messagePrefix = self.config.get("messagePrefix", "^5[AutoMod]^7: ")

        # Session data (resets on map change)
        self._session_violations = {}  # IP -> {count, name, punished_at_counts}

        # Persistent data
        self._violation_log = self._LoadViolationLog()

        # SMOD command list
        self._smodCommandList = {
            tuple(["kickoffenders"]): ("!kickoffenders - Kick all players with violations this session", self.HandleKickOffenders),
            tuple(["tempbanoffenders"]): ("!tempbanoffenders <rounds> - Tempban all offenders for N rounds", self.HandleTempbanOffenders),
            tuple(["amstat", "automodstatus"]): ("!<amstat | automodstatus> - Show automod statistics", self.HandleStatus),
            tuple(["clearmodlog"]): ("!clearmodlog - Clear all violation history from punishedPlayers.json", self.HandleClearLog)
        }

    def _LoadConfig(self) -> dict:
        """Load configuration from automodCfg.json, creating it with defaults if missing"""
        config_path = os.path.join(os.path.dirname(__file__), "automodCfg.json")
        default_config = {
            "enabled": True,
            "prohibitedWords": ["badword"],
            "prohibitedWordsFile": "",
            "threshold": 3,
            "action": 0,
            "muteDuration": 5,
            "tempbanDuration": 3,
            "silentMode": False,
            "messagePrefix": "^5[AutoMod]^7: ",
            "privateMessage": "^1You have been flagged for using prohibited language. Further violations will result in punishment."
        }

        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            else:
                # Create default config
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
                Log.info(f"Created default configuration at {config_path}")
        except Exception as e:
            Log.error(f"Error loading config: {e}. Using defaults.")

        # Load prohibited words from external file if specified
        words_file = default_config.get("prohibitedWordsFile", "")
        if words_file:
            words_from_file = self._LoadProhibitedWordsFile(words_file)
            if words_from_file:
                # If external file is used, replace the prohibitedWords list
                default_config["prohibitedWords"] = words_from_file
                Log.info(f"Loaded {len(words_from_file)} prohibited words from {words_file}")
            else:
                Log.warning(f"Failed to load prohibited words from {words_file}, using config array")

        # Validate action value
        if default_config.get("action", 0) not in [0, 1, 2, 3]:
            Log.warning(f"Invalid action value {default_config.get('action')}. Defaulting to 0 (mute)")
            default_config["action"] = 0

        # Validate threshold
        if default_config.get("threshold", 3) < 1:
            Log.warning(f"Invalid threshold value {default_config.get('threshold')}. Defaulting to 3")
            default_config["threshold"] = 3

        # Warn about empty prohibited words list
        if not default_config.get("prohibitedWords", []):
            Log.warning("Prohibited words list is empty. Plugin will not detect any violations.")

        return default_config

    def _LoadProhibitedWordsFile(self, filename: str) -> list:
        """Load prohibited words from an external text file"""
        try:
            # Support both absolute and relative paths
            if os.path.isabs(filename):
                file_path = filename
            else:
                # Relative to plugin directory
                file_path = os.path.join(os.path.dirname(__file__), filename)

            if not os.path.exists(file_path):
                Log.error(f"Prohibited words file not found: {file_path}")
                return []

            words = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    # Strip whitespace and skip empty lines and comments
                    line = line.strip()
                    if line and not line.startswith('#'):
                        words.append(line)

            return words

        except Exception as e:
            Log.error(f"Error loading prohibited words file: {e}")
            return []

    def _LoadViolationLog(self) -> dict:
        """Load violation log from punishedPlayers.json"""
        log_path = os.path.join(os.path.dirname(__file__), "punishedPlayers.json")
        try:
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            Log.error(f"Error loading violation log: {e}. Starting with empty log.")
        return {}

    def _SaveViolationLog(self):
        """Save violation log to punishedPlayers.json"""
        log_path = os.path.join(os.path.dirname(__file__), "punishedPlayers.json")
        try:
            with open(log_path, 'w') as f:
                json.dump(self._violation_log, f, indent=4)
        except Exception as e:
            Log.error(f"Error saving violation log: {e}")

    def _LogViolation(self, player_ip: str, player_name: str, message: str,
                      matched_words: list, violation_count: int, action_taken: str):
        """Log a violation to the persistent log file"""
        if player_ip not in self._violation_log:
            self._violation_log[player_ip] = []

        violation_entry = {
            "timestamp": datetime.now().isoformat(),
            "player_name": player_name,
            "message": message,
            "matched_words": matched_words,
            "violation_number": violation_count,
            "action_taken": action_taken if action_taken else "warned"
        }

        self._violation_log[player_ip].append(violation_entry)
        self._SaveViolationLog()

    def _ApplyPunishment(self, client: client.Client, violation_count: int, matched_words: list, message: str):
        """Apply punishment based on configured action"""
        action = self.config.get("action", 0)
        player_id = client.GetId()
        player_name = client.GetName()
        player_ip = client.GetIp().split(':')[0]

        action_name = ""

        try:
            if action == 0:  # Mute
                duration = self.config.get("muteDuration", 5)
                self._serverData.interface.ClientMute(player_id, duration)
                action_name = f"muted for {duration} minutes"
                Log.info(f"Muted {player_name} (ID: {player_id}) for {duration} minutes")

            elif action == 1:  # Kick
                self._serverData.interface.ClientKick(player_id)
                action_name = "kicked"
                Log.info(f"Kicked {player_name} (ID: {player_id})")

            elif action == 2:  # Tempban
                duration = self.config.get("tempbanDuration", 3)
                self._serverData.interface.Tempban(player_name, duration)
                action_name = f"tempbanned for {duration} rounds"
                Log.info(f"Tempbanned {player_name} for {duration} rounds")

            elif action == 3:  # Ban (permanent)
                self._serverData.interface.ClientBan(player_ip)
                action_name = "permanently banned"
                Log.info(f"Permanently banned {player_name} (IP: {player_ip})")

            # Update violation log with action taken
            self._LogViolation(player_ip, player_name, message, matched_words, violation_count, action_name)

            # Announce (if not silent)
            if not self.config.get("silentMode", False):
                self._serverData.interface.SvSay(
                    self._messagePrefix + f"^7{player_name} has been {action_name} for chat violations."
                )
        except Exception as e:
            Log.error(f"Error applying punishment: {e}")

    def Start(self) -> bool:
        """Called when plugin starts"""
        if not self.config.get("enabled", True):
            Log.info("AutoMod plugin is disabled in configuration")
            return True

        Log.info("AutoMod plugin started")
        Log.info(f"Monitoring {len(self.config.get('prohibitedWords', []))} prohibited words")
        Log.info(f"Threshold: {self.config.get('threshold', 3)} violations")
        Log.info(f"Action: {self.config.get('action', 0)}")
        Log.info(f"Silent mode: {self.config.get('silentMode', False)}")

        return True

    def Finish(self):
        """Called when plugin stops"""
        # Save violation log one last time
        self._SaveViolationLog()
        Log.info("AutoMod plugin stopped")

    def OnMessage(self, client: client.Client, message: str, teamId: int, data: dict) -> bool:
        """Handle chat messages - check for prohibited words"""
        try:
            if not self.config.get("enabled", True):
                return False

            player_ip = client.GetIp().split(':')[0]  # Strip port
            player_name = client.GetName()
            player_id = client.GetId()

            # Strip color codes and lowercase for matching
            message_clean = colors.StripColorCodes(message).lower()

            # Check for prohibited words
            matched_words = []
            for word in self.config.get("prohibitedWords", []):
                if word.lower() in message_clean:
                    matched_words.append(word)

            # If no matches, return
            if not matched_words:
                return False

            # Increment violation counter
            if player_ip not in self._session_violations:
                self._session_violations[player_ip] = {
                    "count": 0,
                    "name": player_name,
                    "punished_at_counts": []
                }

            self._session_violations[player_ip]["count"] += 1
            self._session_violations[player_ip]["name"] = player_name  # Update to current name
            current_count = self._session_violations[player_ip]["count"]

            Log.info(f"Player {player_name} ({player_ip}) violated chat rules. Count: {current_count}. Matched: {matched_words}")

            # Log violation to persistent storage
            self._LogViolation(player_ip, player_name, message, matched_words, current_count, None)

            # Check if threshold reached
            threshold = self.config.get("threshold", 3)
            will_be_punished = False

            if current_count >= threshold:
                # Check if we've already punished at this count
                if current_count not in self._session_violations[player_ip]["punished_at_counts"]:
                    will_be_punished = True
                    self._ApplyPunishment(client, current_count, matched_words, message)
                    self._session_violations[player_ip]["punished_at_counts"].append(current_count)

            # Send private warning message ONLY if not being punished (if not silent)
            if not self.config.get("silentMode", False) and not will_be_punished:
                private_msg = self.config.get("privateMessage", "You have been flagged.")
                self._serverData.interface.SvTell(player_id, self._messagePrefix + private_msg)

        except Exception as e:
            Log.error(f"Error in OnMessage: {e}")

        return False  # Don't capture event

    def OnMapChange(self, mapName: str, oldMapName: str) -> bool:
        """Handle map change - reset session violations"""
        try:
            Log.info(f"Map changed from {oldMapName} to {mapName}. Resetting session violations.")

            # Clear session data
            self._session_violations.clear()

            # Optionally announce
            if not self.config.get("silentMode", False):
                self._serverData.interface.SvSay(
                    self._messagePrefix + "^2Chat violation counters reset for new map"
                )
        except Exception as e:
            Log.error(f"Error in OnMapChange: {e}")

        return False

    def HandleKickOffenders(self, playerName, smodID, adminIP, cmdArgs):
        """SMOD command: !kickoffenders - Kick all players with violations this session"""
        try:
            if not self.config.get("enabled", True):
                return False

            # Get all clients with violations
            kicked_count = 0
            for player_ip, data in self._session_violations.items():
                if data["count"] > 0:
                    # Find client by IP
                    all_clients = self._serverData.API.GetAllClients()
                    for cl in all_clients:
                        if cl.GetIp().split(':')[0] == player_ip:
                            self._serverData.interface.ClientKick(cl.GetId())
                            Log.info(f"SMOD {playerName} kicked offender {cl.GetName()} (violations: {data['count']})")
                            kicked_count += 1
                            break

            self._serverData.interface.SmSay(
                self._messagePrefix + f"Kicked {kicked_count} offender(s)"
            )
        except Exception as e:
            Log.error(f"Error in HandleKickOffenders: {e}")
            self._serverData.interface.SmSay(self._messagePrefix + f"^1Error: {e}")

        return True

    def HandleTempbanOffenders(self, playerName, smodID, adminIP, cmdArgs):
        """SMOD command: !tempbanoffenders <rounds> - Tempban all offenders for N rounds"""
        try:
            if not self.config.get("enabled", True):
                return False

            if len(cmdArgs) < 2:
                self._serverData.interface.SmSay(
                    self._messagePrefix + "^1Usage: !tempbanoffenders <rounds>"
                )
                return False

            try:
                rounds = int(cmdArgs[1])
            except ValueError:
                self._serverData.interface.SmSay(
                    self._messagePrefix + "^1Invalid duration. Must be a number."
                )
                return False

            # Tempban all offenders
            banned_count = 0
            for player_ip, data in self._session_violations.items():
                if data["count"] > 0:
                    # Find client by IP
                    all_clients = self._serverData.API.GetAllClients()
                    for cl in all_clients:
                        if cl.GetIp().split(':')[0] == player_ip:
                            self._serverData.interface.Tempban(cl.GetName(), rounds)
                            Log.info(f"SMOD {playerName} tempbanned offender {cl.GetName()} for {rounds} rounds (violations: {data['count']})")
                            banned_count += 1
                            break

            self._serverData.interface.SmSay(
                self._messagePrefix + f"Tempbanned {banned_count} offender(s) for {rounds} rounds"
            )
        except Exception as e:
            Log.error(f"Error in HandleTempbanOffenders: {e}")
            self._serverData.interface.SmSay(self._messagePrefix + f"^1Error: {e}")

        return True

    def HandleStatus(self, playerName, smodID, adminIP, cmdArgs):
        """SMOD command: !amstat - Show automod statistics"""
        try:
            total_offenders = len(self._session_violations)
            total_violations = sum(data["count"] for data in self._session_violations.values())
            total_logged = sum(len(logs) for logs in self._violation_log.values())

            self._serverData.interface.SmSay(
                self._messagePrefix + f"^2Session: {total_offenders} offenders, {total_violations} violations | Lifetime: {total_logged} logged"
            )
        except Exception as e:
            Log.error(f"Error in HandleStatus: {e}")
            self._serverData.interface.SmSay(self._messagePrefix + f"^1Error: {e}")

        return True

    def HandleClearLog(self, playerName, smodID, adminIP, cmdArgs):
        """SMOD command: !clearmodlog - Clear all violation history"""
        try:
            # Count entries before clearing
            total_entries = sum(len(logs) for logs in self._violation_log.values())
            total_ips = len(self._violation_log)

            # Clear the violation log
            self._violation_log.clear()
            self._SaveViolationLog()

            Log.info(f"SMOD {playerName} cleared violation log ({total_entries} entries from {total_ips} IPs)")
            self._serverData.interface.SmSay(
                self._messagePrefix + f"^2Cleared {total_entries} violation entries from {total_ips} IP addresses"
            )
        except Exception as e:
            Log.error(f"Error in HandleClearLog: {e}")
            self._serverData.interface.SmSay(self._messagePrefix + f"^1Error: {e}")

        return True

    def HandleSmodCommand(self, playerName, smodID, adminIP, cmdArgs):
        """Dispatch SMOD commands"""
        command = cmdArgs[0]
        if command.startswith("!"):
            command = command[1:]

        for c in self._smodCommandList:
            if command in c:
                return self._smodCommandList[c][1](playerName, smodID, adminIP, cmdArgs)
        return False

    def OnSmsay(self, playerName: str, smodID: int, adminIP: str, message: str) -> bool:
        """Handle admin smsay events"""
        try:
            if not self.config.get("enabled", True):
                return False

            message_lower = message.lower()
            messageParse = message_lower.split()
            return self.HandleSmodCommand(playerName, smodID, adminIP, messageParse)
        except Exception as e:
            Log.error(f"Error in OnSmsay: {e}")
            return False


# Module-level functions required by Godfinger

def OnInitialize(serverData: serverdata.ServerData, exports=None) -> bool:
    """Called once when plugin loads"""
    logMode = logging.INFO
    if serverData.args.debug:
        logMode = logging.DEBUG
    if serverData.args.logfile != "":
        logging.basicConfig(
            filename=serverData.args.logfile,
            level=logMode,
            format='%(asctime)s %(levelname)08s %(name)s %(message)s')
    else:
        logging.basicConfig(
            level=logMode,
            format='%(asctime)s %(levelname)08s %(name)s %(message)s')

    global SERVER_DATA
    SERVER_DATA = serverData

    global PluginInstance
    PluginInstance = AutomodPlugin(serverData)

    # Register SMOD commands
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredSmodCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._smodCommandList:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._smodCommandList[cmd][0]))
    SERVER_DATA.SetServerVar("registeredSmodCommands", newVal)

    return True


def OnStart() -> bool:
    """Called after plugin initialization"""
    startTime = time.time()
    result = PluginInstance.Start()
    if result:
        loadTime = time.time() - startTime
        PluginInstance._serverData.interface.SvSay(
            PluginInstance._messagePrefix + f"AutoMod started in {loadTime:.2f} seconds!"
        )
    return result


def OnLoop():
    """Called on each server loop tick"""
    # No continuous work needed
    pass


def OnFinish():
    """Called before plugin unload"""
    PluginInstance.Finish()


def OnEvent(event) -> bool:
    """Called for every event"""
    global PluginInstance

    try:
        if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
            if event.isStartup:
                return False
            return PluginInstance.OnMessage(event.client, event.message, event.teamId, event.data)

        elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
            return PluginInstance.OnMapChange(event.mapName, event.oldMapName)

        elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
            return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)

    except Exception as e:
        Log.error(f"Error in OnEvent: {e}")

    return False
