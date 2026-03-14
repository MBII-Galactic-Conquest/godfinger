import logging
import godfingerEvent
import pluginExports
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import lib.shared.colors as colors
import os
import database
import lib.shared.client as client
import requests
import ipaddress


SERVER_DATA = None

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "vpnmonitorCfg.json")

# Not a new version just another option

# To get your API keys goto https://findip.net/ and create an account, then create a API key in the dashboard.

# User_Types from findip.net:
# residential: IPs associated with residential internet connections, typically used by individuals in their homes.
# cellular: IPs associated with mobile networks, often used by smartphones and tablets or mobile proxies/crawlers.
# business: IPs associated with business internet connections, which may include offices, data centers, or other commercial entities.
# hosting: IPs associated with hosting providers, which may include servers, virtual private servers (VPS), or cloud services.
# unknown: IPs that could not be classified into the above categories, which may indicate an unrecognized or inconclusive VPN detection result.

# whitelist is used to allow certain IP addresses that may be detected as VPNs but you want to allow them anyway.
# blacklist is used incase the VPN is not recognized by third party services like findip, but you still consider those IP addresses a VPN.

# action 0 = kick only, 1 = ban by ip then kick
CONFIG_FALLBACK = \
"""{
    "apikey":"your_api_key",
    "block":
    [
        "business", "hosting", "cellular"
    ],
    "action":0,
    "svsayOnAction" : true
}
"""
global VPNMonitorConfig
VPNMonitorConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__)


PluginInstance = None

class VPNMonitor():
    def __init__(self, serverData : serverdata.ServerData):
        self._status = 0
        self._serverData = serverData
        self.config = VPNMonitorConfig
        self._messagePrefix = "^9[VPN]^7: "
        if self.config.cfg["apikey"] == "your_api_key":
            self._status = -1
            Log.error("Please specify valid api key in vpnmonitorCfg.json")
        
        self._database : database.ADatabase = None
        dbPath = os.path.join(os.path.dirname(__file__), "vpn.db")
        dbRes = self._serverData.API.CreateDatabase(dbPath, "vpnmonitor")
        if dbRes == database.DatabaseManager.DBM_RESULT_ALREADY_EXISTS or dbRes == database.DatabaseManager.DBM_RESULT_OK:
            self._database = self._serverData.API.GetDatabase("vpnmonitor")
            self._database.ExecuteQuery("""CREATE TABLE IF NOT EXISTS iplist (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        ip varchar(30),
                                        user_type varchar(32),
                                        whitelist boolean DEFAULT 0,
                                        blacklist boolean DEFAULT 0,
                                        date DATETIME DEFAULT CURRENT_TIMESTAMP
                                        )""")
        else:
            Log.error("Failed to create database at %s with code %d", (dbPath, str(dbRes)))
            self._status = -1
    
        self._smodCommandList = \
            {
                tuple(["whitelistip", "wlip"]) : ("!<whitelistip | wlip> <IP or PlayerName> - add IP to VPN whitelist", self.HandleWhitelistIP),
                tuple(["blacklistip", "blip"]) : ("!<blacklistip | blip> <IP or PlayerName> - remove IP from VPN whitelist", self.HandleBlacklistIP),
                tuple(["vpnhitcount", "vpnhits"]) : ("!<vpnhitcount | vpnhits> - show how many VPN hits in database", self.HandleHitCount)
            }

    def Start(self) -> bool:
        allClients = self._serverData.API.GetAllClients()
        if allClients:
            for cl in allClients:
                vpnType = self.GetIpVpnType(cl.GetIp())
                self.ProcessVpnClient(cl, vpnType)
        else:
            Log.debug("No clients connected on plugin start, skipping initial VPN check.")
        if self._status == 0:
            return True
        else:
            return False

    def Finish(self):
        pass

    def OnClientConnect(self, client : client.Client, data : dict) -> bool:
        vpnType = self.GetClientVPNType(client)
        self.ProcessVpnClient(client, vpnType)
        return False
        
    
    def GetClientVPNType(self, client : client.Client) -> str:
        ip = client.GetIp()
        return self.GetIpVpnType(ip)

    def GetIpVpnType(self, ip : str ):
        Log.debug("Getting vpn associated with ip address %s", ip)
        existing = self._database.ExecuteQuery("SELECT user_type FROM iplist WHERE ip=\""+ip+"\"", True)
        vpnType = "unknown" # default to unknown to avoid false positives on blocking
        if existing == None or len(existing) == 0:
            # not in the database, lets check on VPN detection service
            token = self.config.cfg["apikey"]
            try:
                webRequest = requests.get(f"https://api.findip.net/{ip}/?token={token}", timeout=10)  # Timeout for safety
                if webRequest.status_code == 200:
                    jsonified = webRequest.json()  # This can raise JSONDecodeError if not valid JSON
                    if isinstance(jsonified, dict) and "traits" in jsonified and "user_type" in jsonified["traits"]:  # Validate response structure
                        vpnType = jsonified["traits"]["user_type"]
                        self._database.ExecuteQuery("INSERT INTO iplist (ip, user_type) VALUES (%s, %s)" % ("\""+ip+"\"", "\""+vpnType+"\""))
                    else:
                        Log.warning("Unexpected API response structure for IP %s: %s", ip, jsonified)
                else:
                    Log.error("Web request to VPN check service failed with http code %d for IP %s", webRequest.status_code, ip)
            except requests.RequestException as e:
                Log.error("Network error during VPN check for IP %s: %s", ip, e)
            except ValueError as e:  # JSONDecodeError is a subclass of ValueError
                Log.error("Invalid JSON response from VPN API for IP %s: %s", ip, e)
        else:
            Log.debug("VPN ip entry existing in database, using it.")
            vpnType = existing[0][0]
    
        return vpnType

    def ProcessVpnClient(self, client : client.Client, vpnType : str):
        ip = client.GetIp()
        id = client.GetId()

        whitelist = self._database.ExecuteQuery("SELECT ip FROM iplist WHERE ip=\""+ip+"\" AND whitelist=1", True)
        if whitelist and len(whitelist) > 0:
            return

        blockable = self.config.GetValue("block", [])
        if vpnType in blockable:
            Log.debug("Kicking a player with ip %s due to VPN block rules" % ip)
            if self.config.GetValue("action", 0) == 1:
                Log.debug("Banning ip %s" % ip)
                self._serverData.interface.ClientBan(ip)
            self._serverData.interface.ClientKick(id)
            if self.config.cfg["svsayOnAction"] == True:
                self._serverData.interface.SvSay(self._messagePrefix + f"Kicked player {client.GetName()}^7 for suspected VPN usage.")
            return
        
        blacklist = self._database.ExecuteQuery("SELECT ip FROM iplist WHERE ip=\""+ip+"\" AND blacklist=1", True)
        if blacklist and len(blacklist) > 0:
            Log.debug("Kicking a player with ip %s due to VPN blacklist match.", ip)
            if self.config.GetValue("action", 0) == 1:
                Log.debug("Banning ip %s" % ip)
                self._serverData.interface.ClientBan(ip)
            elif self.config.GetValue("action", 0) == 0:
                Log.debug("Kicking ip %s" % ip)
                self._serverData.interface.ClientKick(id)
            if self.config.cfg["svsayOnAction"] == True:
                self._serverData.interface.SvSay(self._messagePrefix + f"Kicked player {client.GetName()}^7 for suspected VPN usage.")
            return

        if vpnType == "unknown":
            Log.warning("Player %s has an unrecognized IP type, VPN detection inconclusive.", client.GetName())
            self._serverData.interface.SmSay(self._messagePrefix + f"Player {client.GetName()}^7 has an unrecognized IP type, VPN detection inconclusive.")

    def _GetClientByName(self, playerName):
        """Find a connected client by name (case-insensitive, color-stripped)"""
        try:
            connected_clients = self._serverData.API.GetAllClients()
            playerName_stripped = colors.StripColorCodes(playerName).lower()

            for cl in connected_clients:
                client_name_stripped = colors.StripColorCodes(cl.GetName()).lower()
                if client_name_stripped == playerName_stripped:
                    return cl
            return None
        except Exception as e:
            Log.error("Error getting client by name: %s", e)
            return None

    def _IsValidIp(self, ip_string):
        """Check if string is a valid IP address"""
        try:
            ipaddress.ip_address(ip_string)
            return True
        except:
            return False

    def HandleWhitelistIP(self, playerName, smodID, adminIP, cmdArgs):
            """Handle !whitelistip command - add IP to whitelist"""
            if len(cmdArgs) < 2:
                message = f"{self._messagePrefix}^7Usage: ^5!whitelistip ^9<IP>"
                self._serverData.interface.SmSay(message)
                Log.info(f"SMOD '{playerName}' used !whitelistip without arguments")
                return False

            target = cmdArgs[1]
            target_ip = None

            if self._IsValidIp(target):
                target_ip = target
            else:
                self._serverData.interface.SmSay(f"{self._messagePrefix}^1Invalid IP address!")
                Log.warning(f"SMOD '{playerName}' tried to VPN whitelist invalid target: {target}")                
                return False

            # Ensure the IP exists in iplist
            existing_ip = self._database.ExecuteQuery("SELECT ip FROM iplist WHERE ip=\""+target_ip+"\"", True)
            if existing_ip is None or len(existing_ip) == 0:
                self._serverData.interface.SmSay(f"{self._messagePrefix}^1IP {target_ip} does not exist in database")
                Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' tried to VPN whitelist an IP that is not in the database: {target_ip}")
                return
            # Check if already whitelisted
            existing_whitelist = self._database.ExecuteQuery("SELECT ip FROM iplist WHERE ip=\""+target_ip+"\" AND whitelist=1", True)
            if existing_whitelist is not None and len(existing_whitelist) > 0:
                self._serverData.interface.SmSay(f"{self._messagePrefix}^3IP {target_ip} is already whitelisted in database.")
                Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' tried to VPN whitelist already listed IP: {target_ip}")
                return
            # Add to whitelist, remove from blacklist if exists
            self._database.ExecuteQuery("UPDATE iplist SET whitelist = 1, blacklist = 0 WHERE ip=\""+target_ip+"\"")
            self._serverData.interface.SmSay(f"{self._messagePrefix}^2Added IP {target_ip} to VPN whitelist.")
            Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' added IP {target_ip} to VPN whitelist.")
            
    def HandleBlacklistIP(self, playerName, smodID, adminIP, cmdArgs):
        """Handle !blacklistip command - remove IP from VPN whitelist"""
        if len(cmdArgs) < 2:
            message = f"{self._messagePrefix}^7Usage: ^5!blacklistip ^9<IP or PlayerName>"
            self._serverData.interface.SmSay(message)
            Log.info(f"SMOD '{playerName}' used !blacklistip without arguments")
            return False

        target = cmdArgs[1]
        target_ip = None

        # Check if target is a valid IP
        if self._IsValidIp(target):
            target_ip = target
        else:
            # Try to find player by name
            target_client = self._GetClientByName(target)
            if target_client:
                target_ip = target_client.GetIp()
                Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' VPN blacklisting player '{target_client.GetName()}' with IP {target_ip}")
            else:
                message = f"{self._messagePrefix}^1Player '{target}' not found or not a valid IP"
                self._serverData.interface.SmSay(message)
                Log.warning(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' tried to VPN blacklist invalid target: {target}")
                return False
            
        # Ensure the IP exists in iplist
        existing_ip = self._database.ExecuteQuery("SELECT ip FROM iplist WHERE ip=\""+target_ip+"\"", True)
        if existing_ip is None or len(existing_ip) == 0:
            self._serverData.interface.SmSay(f"{self._messagePrefix}^1IP {target_ip} does not exist in database")
            Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' tried to VPN blacklist an IP that is not in the database: {target_ip}")
            return
        # Check if already blacklisted
        existing_blacklist = self._database.ExecuteQuery("SELECT ip FROM iplist WHERE ip=\""+target_ip+"\" AND blacklist=1", True)
        if existing_blacklist is not None and len(existing_blacklist) > 0:
            self._serverData.interface.SmSay(f"{self._messagePrefix}^3IP {target_ip} is already blacklisted in database.")
            Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' tried to VPN blacklist already blacklisted IP: {target_ip}")
            return
        # Add to blacklist, remove from whitelist if exists
        self._database.ExecuteQuery("UPDATE iplist SET blacklist = 1, whitelist = 0 WHERE ip=\""+target_ip+"\"")
        self._serverData.interface.SmSay(f"{self._messagePrefix}^1Added IP {target_ip} to VPN blacklist. They still need to be kicked!")
        Log.info(f"SMOD '{playerName}' SmodID '{smodID}' AdminIP '{adminIP}' added IP {target_ip} to VPN blacklist.")

    def HandleHitCount(self, playerName, smodId, adminIP, cmdArgs):
        """Handle !vpnhitcount command - show how many VPNs hit in database"""
        if len(cmdArgs) < 2:
            vpnhits = self._database.ExecuteQuery("SELECT COUNT(*) FROM iplist WHERE user_type IN (\""+ "\", \"".join(self.config.GetValue("block", [])) +"\")", True)
            message = f"{self._messagePrefix}^7Total TKPadas wrecked: ^5{vpnhits[0][0]}"
            self._serverData.interface.SmSay(message)
            Log.info(f"SMOD '{playerName}' used !vpnhitcount command. Total VPN hits: {vpnhits[0][0]}")
        return


    def HandleSmodCommand(self, playerName, smodId, adminIP, cmdArgs):
        command = cmdArgs[0]
        if command.startswith("!"):
            if command.startswith("!"):
                command = command[len("!"):]
        for c in self._smodCommandList:
            if command in c:
                return self._smodCommandList[c][1](playerName, smodId, adminIP, cmdArgs)
        return False

    def OnSmsay(self, playerName, smodID, adminIP, message):
        """Handle SMSAY events"""
        message = message.lower()
        messageParse = message.split()
        return self.HandleSmodCommand(playerName, smodID, adminIP, messageParse)

    def OnClientDisconnect(self, client : client.Client, reason, data ) -> bool:
        return False

# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    global SERVER_DATA
    SERVER_DATA = serverData # keep it stored
    global PluginInstance
    PluginInstance = VPNMonitor(serverData)
    if exports != None:
        pass
    
    if PluginInstance._status < 0:
        Log.error("VPNMonitor plugin failed to initialize")
        return False

    # Register smod commands
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredSmodCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._smodCommandList:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._smodCommandList[cmd][0]))
    SERVER_DATA.SetServerVar("registeredSmodCommands", newVal)

    return True # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    from time import time
    startTime = time()
    result = PluginInstance.Start()
    if result:
        loadTime = time() - startTime
        PluginInstance._serverData.interface.SvSay(
            PluginInstance._messagePrefix + f"VPN Monitor started in {loadTime:.2f} seconds!"
        )
    return result

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass
    #print("Calling Loop function from plugin!")

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        if event.isStartup:
            return False #Ignore startup messages
        else:
            return PluginInstance.OnClientConnect(event.client, event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        if event.isStartup:
            return False #Ignore startup messages
        else:
            return PluginInstance.OnClientDisconnect(event.client, event.reason, event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return False
    return False

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()