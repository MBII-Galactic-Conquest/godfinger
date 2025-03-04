
import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.config as config;
import os;
import lib.shared.client as client;
import re;

SERVER_DATA = None;

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "automodCfg.json");

# > action 0 - mute
# > action 1 - kick
# > action 2 - tempban

CONFIG_FALLBACK = \
"""{
    "wordsBlacklist":
    [

    ],
    "namesBlacklist":
    [

    ],
    "action":1
}
"""

global AutomodConfig;
AutomodConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

Log = logging.getLogger(__name__);

PluginInstance = None;

class Automod():
    def __init__(self, serverData : serverdata.ServerData):
        self._serverData = serverData;
        self.config = AutomodConfig;

    def OnClientMessage(self, client : client.Client, message : str, teamId : int) -> bool:
        if not self.FilterString(message):
            pass; # todo
        return False;

    def OnClientConnect(self, client : client.Client) -> bool:
        name = client.GetName();
        if not self.FilterString(name):
            pass; # todo
        return False;

    def OnClientChanged(self, client : client.Client, data : dict) -> bool:
        newName = None;
        if "n" in data:
            newName = data["n"];
        elif "name" in data:
            newName = data["name"];
        else:
            return False;
        
        if not self.FilterString(newName):
            pass; # todo

    def FilterString(self, string : str) -> bool:
        return True;


# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
    logMode = logging.INFO;
    if serverData.args.debug:
        logMode = logging.DEBUG;
    if serverData.args.logfile != "":
        logging.basicConfig(
        filename=serverData.args.logfile,
        level=logMode,
        format='%(asctime)s %(levelname)08s %(name)s %(message)s')
    else:
        logging.basicConfig(
        level=logMode,
        format='%(asctime)s %(levelname)08s %(name)s %(message)s')

    global SERVER_DATA;
    SERVER_DATA = serverData; 
    global PluginInstance;
    PluginInstance = Automod(serverData);
    if exports != None:
        pass;
    return True; 

def OnStart():
    return True; 

def OnLoop():
    pass

def OnFinish():
    pass;

def OnEvent(event) -> bool:
    global PluginInstance;
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return PluginInstance.OnClientMessage(event.client, event.message, event.teamId);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return PluginInstance.OnClientConnect(event.client);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return PluginInstance.OnClientChanged(event.client, event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return False;
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