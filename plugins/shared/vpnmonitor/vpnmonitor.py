
import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.config as config;
import os;
import database;
import lib.shared.client as client;
import requests;

SERVER_DATA = None;

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "vpnmonitorCfg.json");

# To get your API keys go to https://iphub.info/api

# block means as followed by iphub docs 
# block: 0 - Residential or business IP (i.e. safe IP)
# block: 1 - Non-residential IP (hosting provider, proxy, etc.)
# block: 2 - Non-residential & residential IP (warning, may flag innocent people)

# blacklist is used incase the VPN is not recognized by third party services like iphub, but you still consider those IP addresses a VPN
#   it will not be listed in database.
# action 0 = kick only, 1 = ban by ip then kick
CONFIG_FALLBACK = \
"""{
    "apikey":"your_api_key",
    "block":
    [
        1, 2
    ],
    "action":0,
    "whitelist":
    [
        "127.0.0.1"
    ],
    "blacklist":
    [
    
    ],
    "svsayOnAction" : true
}
"""

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__);

PluginInstance = None;

class vpnMonitorPlugin(object): # Match the class name used in OnInitialize
    def __init__(self, serverData : serverdata.ServerData):
        self._serverData = serverData
        self._status = 0
        
        self.target_port = getattr(serverData, 'config', {}).get('portFilter')
        
        cfg_name = f"vpnmonitorCfg_{self.target_port}.json" if self.target_port else "vpnmonitorCfg.json"
        self.config_path = os.path.join(os.path.dirname(__file__), cfg_name)
        
        self.config = config.Config.fromJSON(self.config_path, CONFIG_FALLBACK)
        self._messagePrefix = "^9[VPN]^7: "

        if self.config.cfg.get("apikey") == "your_api_key":
            self._status = -1
            Log.error(f"Please specify valid api key in {cfg_name}")
        
        # Database setup
        db_file = f"vpn_{self.target_port}.db" if self.target_port else "vpn.db"
        db_id = f"vpnmonitor_{self.target_port}" if self.target_port else "vpnmonitor"
        dbPath = os.path.join(os.path.dirname(__file__), db_file)
        
        dbRes = self._serverData.API.CreateDatabase(dbPath, db_id)
        if dbRes in [database.DatabaseManager.DBM_RESULT_ALREADY_EXISTS, database.DatabaseManager.DBM_RESULT_OK]:
            self._database = self._serverData.API.GetDatabase(db_id)
            self._database.ExecuteQuery("""CREATE TABLE IF NOT EXISTS iplist (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        ip varchar(30),
                                        vpn int,
                                        date DATETIME DEFAULT CURRENT_TIMESTAMP
                                        );""")
        else:
            Log.error(f"DB Error: {dbRes}")
            self._status = -1

    def _get_interface(self):
        """Returns the interface for the specific target port"""
        if hasattr(self._serverData, 'interfaceMap') and self.target_port:
            return self._serverData.interfaceMap.get(int(self.target_port))
        return self._serverData.interface          

    def Start(self) -> bool:
        allClients = self._serverData.API.GetAllClients();
        for cl in allClients:
            vpnType = self.GetIpVpnType(cl.GetIp());
            self.ProcessVpnClient(cl, vpnType);
        if self._status == 0:
            return True;
        else:
            return False;

    def Finish(self):
        pass;

    def OnClientConnect(self, client : client.Client, data : dict) -> bool:
        vpnType = self.GetClientVPNType(client);
        if vpnType < 0:
            return False;
        self.ProcessVpnClient(client, vpnType);
        return False;
        
    
    def GetClientVPNType(self, client : client.Client) -> int:
        ip = client.GetIp();
        return self.GetIpVpnType(ip);
        

    def GetIpVpnType(self, ip : str ) -> int:
        whitelist = self.config.cfg["whitelist"];
        if ip in whitelist:
            Log.debug("IP %s is whitelisted, skipping VPN check.", ip);
            return -1;
    
        Log.debug("Getting vpn associated with ip address %s", ip);
        existing = self._database.ExecuteQuery("SELECT vpn FROM iplist WHERE ip=\""+ip+"\"", True);
        vpnType = -1;
        if existing == None or len(existing) == 0:
            # not in the database, lets check on VPN detection service
            payload = {'key': self.config.cfg["apikey"]};
            webRequest = requests.get(f"http://v2.api.iphub.info/ip/{ip}", params = payload);
            if webRequest.status_code == 200:
                jsonified = webRequest.json();
                if "block" in jsonified:
                    vpnType = jsonified["block"];
                    fmt = "INSERT INTO iplist (ip, vpn) VALUES (%s, %d);" % ("\""+ip+"\"", vpnType);
                    self._database.ExecuteQuery(fmt);
            else:
                Log.error("Web request to VPN check service is failed with http code %d", webRequest.status_code);
        else:
            Log.debug("VPN ip entry existing in database, using it.");
            vpnType = existing[0][0];
        
        return vpnType;

    def ProcessVpnClient(self, client : client.Client, vpnType : int):
        ip = client.GetIp()
        id = client.GetId()
        blockable = self.config.GetValue("block", []);
        if vpnType in blockable:
            Log.debug("Kicking a player with ip %s due to VPN block rules" % ip);
            if self.config.GetValue("action", 0) == 1:
                Log.debug("Banning ip %s" % ip)
                self._get_interface().ClientBan(ip);
            self._get_interface().ClientKick(id);
            if self.config.cfg["svsayOnAction"] == True:
                self._get_interface().SvSay(self._messagePrefix + f"Kicked player {client.GetName()}^7 for suspected VPN usage.")
            return;
        
        blacklist = self.config.cfg["blacklist"];
        if ip in blacklist:
            Log.debug("Kicking a player with ip %s due to VPN blacklist rules" % ip);
            if self.config.GetValue("action", 0) == 1:
                Log.debug("Banning ip %s" % ip)
                self._get_interface().ClientBan(ip);
            self._get_interface().ClientKick(id);
            if self.config.cfg["svsayOnAction"] == True:
                self._get_interface().SvSay(self._messagePrefix + f"Kicked player {client.GetName()}^7 for suspected VPN usage.")
            return;

    def OnClientDisconnect(self, client : client.Client, reason, data ) -> bool:
        return False;


# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    global SERVER_DATA;
    SERVER_DATA = serverData; # keep it stored
    global PluginInstance;
    PluginInstance = vpnMonitorPlugin(serverData)
    if exports != None:
        pass;
    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance;
    return PluginInstance.Start();

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass
    #print("Calling Loop function from plugin!");

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance
    if not PluginInstance:
        return False

    # Check if the event came from the port this plugin is assigned to
    event_port = event.data.get('source_port') if event.data else None
    target = getattr(PluginInstance, 'target_port', None)
    
    if target and event_port and int(event_port) != int(target):
        return False # Ignore events from other server instances   

    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        if event.isStartup:
            return False; #Ignore startup messages
        else:
            return PluginInstance.OnClientConnect(event.client, event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        if event.isStartup:
            return False; #Ignore startup messages
        else:
            return PluginInstance.OnClientDisconnect(event.client, event.reason, event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return False;
    return False;

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()