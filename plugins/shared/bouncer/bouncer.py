"""
Bouncer Plugin - New IP Gate System

Tracks IP addresses of players joining the server.
- Known IPs (in ipList.json) pass through without punishment
- New/unknown IPs receive configurable punishments (marktk, mute, or both)

Actions:
    0 = marktk only
    1 = mute only
    2 = mute AND marktk

SMOD Commands:
    !cleargateips - Clears the bouncer IP whitelist

Note: If antipadawan plugin is active, bouncer will skip punishment for players
whose names match antipadawan's detectedWords list to avoid duplicate punishments.
"""

import os
import re
import json
import logging
from datetime import datetime
from time import time

import godfingerEvent
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import lib.shared.client as client
import lib.shared.colors as colors

SERVER_DATA = None
Log = logging.getLogger(__name__)

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "bouncerCfg.json")
IP_LIST_PATH = os.path.join(os.path.dirname(__file__), "ipList.json")
ANTIPADAWAN_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "antipadawan", "antipadawanCfg.json")

CONFIG_FALLBACK = """{
    "enabled": true,
    "action": 0,
    "marktkDuration": 60,
    "muteDuration": 15,
    "silentMode": false,
    "messagePrefix": "^3[Bouncer]^7: ",
    "privateMessage": "This is a one-time authentication and will not occur again."
}"""

BouncerConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

PluginInstance = None


class BouncerPlugin:
    def __init__(self, serverData: serverdata.ServerData):
        self._serverData = serverData
        self._status = 0
        self.config = BouncerConfig
        self._messagePrefix = self.config.cfg.get("messagePrefix", "^3[Bouncer]^7: ")

        # Validate action value
        if self.config.cfg.get("action", 0) not in [0, 1, 2]:
            Log.warning(f"Invalid action value {self.config.cfg.get('action')}, defaulting to 0")
            self.config.cfg["action"] = 0

        # Load IP list
        self._ipList = self._LoadIpList()

        # Load antipadawan config if available (to avoid duplicate punishments)
        self._antipadawanConfig = self._LoadAntipadawanConfig()

        # SMOD command registration
        self._smodCommandList = {
            tuple(["cleargateips"]): ("!cleargateips - Clears the bouncer IP whitelist", self.HandleClearGateIps),
        }

    def _LoadAntipadawanConfig(self) -> dict:
        """Load antipadawan config to check for name conflicts"""
        try:
            if os.path.exists(ANTIPADAWAN_CONFIG_PATH):
                with open(ANTIPADAWAN_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                    if cfg.get("enabled", True):
                        Log.info("Antipadawan config loaded - will skip punishment for matching names")
                        return cfg
                    else:
                        Log.info("Antipadawan plugin is disabled - no name conflict checking")
                        return None
        except Exception as e:
            Log.debug(f"Antipadawan config not found or error loading: {e}")
        return None

    def _WouldTriggerAntipadawan(self, client_obj: client.Client) -> bool:
        """Check if player name would trigger antipadawan punishment"""
        if self._antipadawanConfig is None:
            return False

        try:
            name = client_obj.GetName()
            name_stripped = colors.StripColorCodes(name).lower()

            # Remove special characters and digits (same logic as antipadawan)
            name_clean = re.sub(r"[:\-.,;=/\\|`~\"'\[\]\(\)_\d]", "", name_stripped)

            # Get detected words from antipadawan config
            detected_words = []
            if "detectedWords" in self._antipadawanConfig:
                detected_words = [word.lower() for word in self._antipadawanConfig["detectedWords"]]
            elif "detectedWord" in self._antipadawanConfig:
                detected_words = [self._antipadawanConfig["detectedWord"].lower()]

            if not detected_words:
                return False

            # Get strictMatch setting
            strict_match = self._antipadawanConfig.get("strictMatch", False)

            # Check if any blocked word matches
            for word in detected_words:
                if strict_match:
                    if name_clean == word:
                        Log.debug(f"Name '{name}' would trigger antipadawan (strict match: '{word}')")
                        return True
                else:
                    if word in name_clean:
                        Log.debug(f"Name '{name}' would trigger antipadawan (loose match: '{word}')")
                        return True

            return False
        except Exception as e:
            Log.error(f"Error checking antipadawan name match: {e}")
            return False

    def _LoadIpList(self) -> dict:
        """Load IP list from ipList.json"""
        try:
            if os.path.exists(IP_LIST_PATH):
                with open(IP_LIST_PATH, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            Log.error(f"Error loading IP list: {e}. Starting with empty list.")
        return {}

    def _SaveIpList(self):
        """Save IP list to ipList.json"""
        try:
            with open(IP_LIST_PATH, 'w', encoding='utf-8') as f:
                json.dump(self._ipList, f, indent=4)
        except Exception as e:
            Log.error(f"Error saving IP list: {e}")

    def _AddOrUpdateIp(self, ip: str, alias: str):
        """Add new IP or update existing entry with new alias"""
        now = datetime.now().isoformat()

        if ip in self._ipList:
            # Update existing entry - update lastAlias and lastSeen
            self._ipList[ip]["lastAlias"] = alias
            self._ipList[ip]["lastSeen"] = now
            Log.debug(f"Updated existing IP {ip} with alias {alias}")
        else:
            # New IP - create entry
            self._ipList[ip] = {
                "firstAlias": alias,
                "lastAlias": alias,
                "firstSeen": now,
                "lastSeen": now
            }
            Log.info(f"Added new IP {ip} with alias {alias}")

        self._SaveIpList()

    def _IsKnownIp(self, ip: str) -> bool:
        """Check if IP exists in the database"""
        return ip in self._ipList

    def _ApplyPunishment(self, client_obj: client.Client):
        """Apply punishment based on configured action"""
        action = self.config.cfg.get("action", 0)
        player_id = client_obj.GetId()
        player_name = client_obj.GetName()

        marktk_duration = self.config.cfg.get("marktkDuration", 60)
        mute_duration = self.config.cfg.get("muteDuration", 15)

        try:
            if action == 0:  # MarkTK only
                self._serverData.interface.MarkTK(player_id, marktk_duration)
                Log.info(f"Marked TK for new player {player_name} (ID: {player_id}) for {marktk_duration} minutes")

            elif action == 1:  # Mute only
                self._serverData.interface.ClientMute(player_id, mute_duration)
                Log.info(f"Muted new player {player_name} (ID: {player_id}) for {mute_duration} minutes")

            elif action == 2:  # Mute AND MarkTK
                self._serverData.interface.MarkTK(player_id, marktk_duration)
                self._serverData.interface.ClientMute(player_id, mute_duration)
                Log.info(f"Marked TK ({marktk_duration}m) and muted ({mute_duration}m) new player {player_name} (ID: {player_id})")

            # Send private message (if not silent)
            if not self.config.cfg.get("silentMode", False):
                private_msg = self.config.cfg.get("privateMessage", "Welcome to the server!")
                self._serverData.interface.SvTell(player_id, self._messagePrefix + private_msg)

        except Exception as e:
            Log.error(f"Error applying punishment to {player_name}: {e}")

    def Start(self) -> bool:
        """Called when plugin starts"""
        if not self.config.cfg.get("enabled", True):
            Log.info("Bouncer plugin is disabled in configuration")
            return True

        Log.info("Bouncer plugin started")
        Log.info(f"Tracking {len(self._ipList)} known IPs")
        Log.info(f"Action: {self.config.cfg.get('action', 0)} (0=marktk, 1=mute, 2=both)")
        Log.info(f"MarkTK duration: {self.config.cfg.get('marktkDuration', 60)} minutes")
        Log.info(f"Mute duration: {self.config.cfg.get('muteDuration', 15)} minutes")
        if self._antipadawanConfig:
            Log.info("Antipadawan integration active - will skip punishment for matching names")
        return True

    def Finish(self):
        """Called when plugin stops"""
        self._SaveIpList()
        Log.info("Bouncer plugin stopped")

    def OnClientBegin(self, client_obj: client.Client, data: dict) -> bool:
        """Handle client begin - check IP and apply punishment if new"""
        try:
            if not self.config.cfg.get("enabled", True):
                return False

            player_ip = client_obj.GetIp()
            player_name = client_obj.GetName()

            if self._IsKnownIp(player_ip):
                # Known IP - update lastAlias and lastSeen, no punishment
                self._AddOrUpdateIp(player_ip, player_name)
                Log.debug(f"Known IP {player_ip} ({player_name}) - no punishment")
            else:
                # New IP - add to database
                Log.info(f"New IP detected: {player_ip} ({player_name})")
                self._AddOrUpdateIp(player_ip, player_name)

                # Check if antipadawan would handle this player (avoid duplicate punishments)
                if self._WouldTriggerAntipadawan(client_obj):
                    Log.info(f"Skipping bouncer punishment for {player_name} - antipadawan will handle")
                else:
                    self._ApplyPunishment(client_obj)

        except Exception as e:
            Log.error(f"Error in OnClientBegin: {e}")

        return False  # Don't capture event

    def HandleClearGateIps(self, playerName, smodID, adminIP, cmdArgs):
        """SMOD command: !cleargateips - Clear all IPs from the database"""
        try:
            ip_count = len(self._ipList)
            self._ipList.clear()
            self._SaveIpList()

            Log.info(f"SMOD {playerName} cleared {ip_count} IPs from bouncer database")
            self._serverData.interface.SmSay(
                self._messagePrefix + f"^2Cleared {ip_count} IPs from the bouncer database"
            )
        except Exception as e:
            Log.error(f"Error in HandleClearGateIps: {e}")
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
            if not self.config.cfg.get("enabled", True):
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
    PluginInstance = BouncerPlugin(serverData)

    # Register SMOD commands (for !help display)
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredSmodCommands")
    if rCommands is not None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._smodCommandList:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._smodCommandList[cmd][0]))
    SERVER_DATA.SetServerVar("registeredSmodCommands", newVal)

    return True


def OnStart() -> bool:
    """Called after plugin initialization"""
    startTime = time()
    result = PluginInstance.Start()
    if result:
        loadTime = time() - startTime
        PluginInstance._serverData.interface.SvSay(
            PluginInstance._messagePrefix + f"Bouncer started in {loadTime:.2f} seconds!"
        )
    return result


def OnLoop():
    """Called on each server loop tick"""
    pass


def OnFinish():
    """Called before plugin unload"""
    PluginInstance.Finish()


def OnEvent(event) -> bool:
    """Called for every event"""
    global PluginInstance

    try:
        if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
            if event.isStartup:
                return False
            return PluginInstance.OnClientBegin(event.client, event.data)

        elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
            return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)

    except Exception as e:
        Log.error(f"Error in OnEvent: {e}")

    return False


if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system.")
    print("Please run one of the start scripts in the start directory to use it.")
    input("Press Enter to close this message.")
    exit()
