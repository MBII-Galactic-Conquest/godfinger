
import logging
import godfingerEvent
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import lib.shared.client as client
import lib.shared.colors as colors
import ipaddress
import re
import os

SERVER_DATA = None

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "whitelistCfg.json")

CONFIG_FALLBACK = \
"""{
    "enabled": true,
    "matchMode": "separate",
    "action": 0,
    "svsayOnAction": true,
    "messagePrefix": "^1[Whitelist]^7: ",
    "ipWhitelist": [
        "127.0.0.1"
    ],
    "aliasWhitelist": [
    ]
}
"""
global WhitelistConfig
WhitelistConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__)


PluginInstance = None

class Whitelist():
    def __init__(self, serverData : serverdata.ServerData):
        self._status = 0
        self._serverData = serverData
        self.config = WhitelistConfig
        self._messagePrefix = self.config.cfg["messagePrefix"]

        # Validate configuration
        if self.config.cfg["matchMode"] not in ["separate", "both"]:
            Log.error("Invalid matchMode '%s', defaulting to 'separate'", self.config.cfg["matchMode"])
            self.config.cfg["matchMode"] = "separate"

        if self.config.cfg["action"] not in [0, 1]:
            Log.error("Invalid action value %d, defaulting to 0", self.config.cfg["action"])
            self.config.cfg["action"] = 0

    def Start(self) -> bool:
        allClients = self._serverData.API.GetAllClients()
        for cl in allClients:
            if self.config.cfg["enabled"]:
                if not self._CheckWhitelist(cl):
                    self._BlockClient(cl, "not on whitelist")
        if self._status == 0:
            return True
        else:
            return False

    def Finish(self):
        pass

    def OnClientConnect(self, client : client.Client, data : dict) -> bool:
        # Check if plugin is enabled
        if not self.config.cfg["enabled"]:
            return False

        # Check whitelist
        if self._CheckWhitelist(client):
            # Player is whitelisted - allow
            Log.debug("Player %s (%s) is whitelisted", client.GetName(), client.GetIp())
            return False
        else:
            # Player not whitelisted - block
            self._BlockClient(client, "not on whitelist")
            return False  # Don't capture event


    def _IsIpMatch(self, ip: str, item) -> bool:
        try:
            target_ip = ipaddress.ip_address(ip)
            if isinstance(item, str):
                return target_ip == ipaddress.ip_address(item)
            elif isinstance(item, list) and len(item) == 2:
                start_ip = ipaddress.ip_address(item[0])
                end_ip = ipaddress.ip_address(item[1])
                return start_ip <= target_ip <= end_ip
        except Exception as e:
            Log.error(f"Error checking IP {ip} against {item}: {e}")
        return False

    def _IsAliasMatch(self, alias: str, whitelistEntry: str) -> bool:
        try:
            # Strip color codes and convert to lowercase
            alias_stripped = colors.StripColorCodes(alias).lower()
            whitelist_stripped = colors.StripColorCodes(whitelistEntry).lower()
            return alias_stripped == whitelist_stripped
        except Exception as e:
            Log.error(f"Error matching alias '{alias}': {e}")
            return False

    def _CheckWhitelist(self, client: client.Client) -> bool:
        ip = client.GetIp()
        name = client.GetName()
        matchMode = self.config.cfg["matchMode"]

        # Check IP whitelist
        ip_matched = False
        for entry in self.config.cfg["ipWhitelist"]:
            if self._IsIpMatch(ip, entry):
                ip_matched = True
                Log.debug("IP %s matches whitelist entry %s", ip, str(entry))
                break

        # Check alias whitelist
        alias_matched = False
        for entry in self.config.cfg["aliasWhitelist"]:
            if self._IsAliasMatch(name, entry):
                alias_matched = True
                Log.debug("Alias '%s' matches whitelist entry '%s'", name, entry)
                break

        # Apply match mode logic
        if matchMode == "separate":
            return ip_matched or alias_matched
        elif matchMode == "both":
            return ip_matched and alias_matched
        else:
            Log.error("Invalid matchMode: %s, defaulting to 'separate'", matchMode)
            return ip_matched or alias_matched

    def _BlockClient(self, client : client.Client, reason : str):
        ip = client.GetIp()
        id = client.GetId()
        name = client.GetName()

        Log.info("Blocking player %s (ID: %d, IP: %s) - %s", name, id, ip, reason)

        # Ban if action == 1
        if self.config.GetValue("action", 0) == 1:
            Log.debug("Banning IP %s", ip)
            self._serverData.interface.ClientBan(ip)

        # Always kick
        self._serverData.interface.ClientKick(id)

        # Broadcast if enabled
        if self.config.cfg["svsayOnAction"] == True:
            self._serverData.interface.SvSay(
                self._messagePrefix + f"Blocked player {name}^7 - not on whitelist"
            )


# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    global SERVER_DATA
    SERVER_DATA = serverData # keep it stored
    global PluginInstance
    PluginInstance = Whitelist(serverData)
    if exports != None:
        pass

    if PluginInstance._status < 0:
        Log.error("Whitelist plugin failed to initialize")
        return False

    return True # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    return PluginInstance.Start()

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        if event.isStartup:
            return False # Ignore startup messages
        else:
            return PluginInstance.OnClientConnect(event.client, event.data)
    return False

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()
