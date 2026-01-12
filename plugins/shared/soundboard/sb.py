import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import lib.shared.client as client
import subprocess
import json
import sys
import os
import time

SERVER_DATA = None;
Log = logging.getLogger(__name__);

## !! Check soundscatalog.txt !! ##
## Sound paths are not based on local, but use PK3 file hierarchy #
## Ensure file extension is included #

PLACEHOLDER = "placeholder"
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "sbConfig.json");
PYTHON_CMD = sys.executable

class soundBoardPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData : serverdata.ServerData = serverData
        self._messagePrefix = colors.ColorizeText("[SB]", "lblue") + ": "
        self.player_join_sound_path = None
        self.player_leave_sound_path = None
        self.message_global_sound_path = None
        self.player_start_sound_path = None

class ClientInfo():
  def __init__(self):
    self.hasBeenGreeted = False # Tracks if they've been greeted
    # Enter more conditions if you desire for client info
ClientsData : dict[int, ClientInfo] = {};

def SV_LoadJson():

    FALLBACK_JSON = {
        "PLAYERJOIN_SOUND_PATH": "placeholder",
        "PLAYERLEAVE_SOUND_PATH": "placeholder",
        "MESSAGEGLOBAL_SOUND_PATH": "placeholder",
        "PLAYERSTART_SOUND_PATH": "placeholder"
    }

    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as file:
            json.dump(FALLBACK_JSON, file, indent=4)
        Log.info(f"Created {CONFIG_FILE} with default fallback values.")
    
    with open(CONFIG_FILE, "r") as file:
        CONFIG = json.load(file)

    if any(PLACEHOLDER in str(value) for value in CONFIG.values()):
        Log.error(f"Placeholder values found in {CONFIG_FILE}, please fill out sbConfig.json and return...")
        sys.exit(0)

    PLAYERJOIN_SOUND_PATH = CONFIG["PLAYERJOIN_SOUND_PATH"]
    PLAYERLEAVE_SOUND_PATH = CONFIG["PLAYERLEAVE_SOUND_PATH"]
    MESSAGEGLOBAL_SOUND_PATH = CONFIG["MESSAGEGLOBAL_SOUND_PATH"]
    PLAYERSTART_SOUND_PATH = CONFIG["PLAYERSTART_SOUND_PATH"]

    return PLAYERJOIN_SOUND_PATH, PLAYERLEAVE_SOUND_PATH, MESSAGEGLOBAL_SOUND_PATH, PLAYERSTART_SOUND_PATH;

def SV_PlayerJoin(PLAYERJOIN_SOUND_PATH):
    global PluginInstance

    if PLAYERJOIN_SOUND_PATH is None or PLAYERJOIN_SOUND_PATH == "" or PLAYERJOIN_SOUND_PATH == PLACEHOLDER:
        Log.error(f"{PLAYERJOIN_SOUND_PATH} is null or using placeholder, exiting...")
        sys.exit(0)

    if PLAYERJOIN_SOUND_PATH == "void":
        return;

    PluginInstance._serverData.interface.SvSound(f"{PLAYERJOIN_SOUND_PATH}")
    Log.info(f"{PLAYERJOIN_SOUND_PATH} has been played to all players...")

    return;

def SV_PlayerLeave(PLAYERLEAVE_SOUND_PATH):
    global PluginInstance

    if PLAYERLEAVE_SOUND_PATH is None or PLAYERLEAVE_SOUND_PATH == "" or PLAYERLEAVE_SOUND_PATH == PLACEHOLDER:
        Log.error(f"{PLAYERLEAVE_SOUND_PATH} is null or using placeholder, exiting...")
        sys.exit(0)

    if PLAYERLEAVE_SOUND_PATH == "void":
        return;

    PluginInstance._serverData.interface.SvSound(f"{PLAYERLEAVE_SOUND_PATH}")
    Log.info(f"{PLAYERLEAVE_SOUND_PATH} has been played to all players...")

    return;

def SV_MessageGlobal(MESSAGEGLOBAL_SOUND_PATH):
    global PluginInstance

    if MESSAGEGLOBAL_SOUND_PATH is None or MESSAGEGLOBAL_SOUND_PATH == "" or MESSAGEGLOBAL_SOUND_PATH == PLACEHOLDER:
        Log.error(f"{MESSAGEGLOBAL_SOUND_PATH} is null or using placeholder, exiting...")
        sys.exit(0)

    if MESSAGEGLOBAL_SOUND_PATH == "void":
        return;

    PluginInstance._serverData.interface.SvSound(f"{MESSAGEGLOBAL_SOUND_PATH}")
    Log.info(f"{MESSAGEGLOBAL_SOUND_PATH} has been played to all players...")

    return;

def SV_EmptyAllClients():
    global ClientsData

    ClientsData.clear()

    return ClientsData;

def CL_PlayerStart(PLAYERSTART_SOUND_PATH, cl : client.Client):
    global PluginInstance

    ID = cl.GetId()
    NAME = cl.GetName()

    if PLAYERSTART_SOUND_PATH is None or PLAYERSTART_SOUND_PATH == "" or PLAYERSTART_SOUND_PATH == PLACEHOLDER:
        Log.error(f"{PLAYERSTART_SOUND_PATH} is null or using placeholder, exiting...")
        sys.exit(0)

    if PLAYERSTART_SOUND_PATH == "void":
        return;

    if ID in ClientsData:   # check if client is present ( shouldnt be negative anyway )
        if ClientsData[ID].hasBeenGreeted == False: # check if client wasnt greeted yet
            PluginInstance._serverData.interface.ClientSound(f"{PLAYERSTART_SOUND_PATH}", ID)
            Log.info(f"{PLAYERSTART_SOUND_PATH} has been played to Client {ID}...")
            PluginInstance._serverData.interface.SvSay(f"{NAME} ^7has made it into the server.")
            ClientsData[ID].hasBeenGreeted = True; # we greeted them, now the above check wont pass again
    else:
        return;

    return ClientsData[ID].hasBeenGreeted;

def CL_OnConnect(cl: client.Client):
    ID = cl.GetId()

    if ID not in ClientsData:
        ClientsData[ID] = ClientInfo() # Create entry for new client
        #Log.info(f"Client {ID} connection stored...")

    return;

def CL_OnDisconnect(cl: client.Client):
    ID = cl.GetId()

    if ID in ClientsData:
        del ClientsData[ID] # Remove client entry from the dictionary
        #Log.info(f"Client {ID} disconnected, removing from dictionary...")

    return;

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
    SERVER_DATA = serverData; # keep it stored
    if exports != None:
        pass;
    global PluginInstance;
    PluginInstance = soundBoardPlugin(serverData)

    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    (PluginInstance.player_join_sound_path,
     PluginInstance.player_leave_sound_path,
     PluginInstance.message_global_sound_path,
     PluginInstance.player_start_sound_path) = SV_LoadJson()
    startTime = time.time()
    loadTime = time.time() - startTime
    PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + f"Soundboard started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    #print("Calling OnEvent function from plugin with event %s!" % (str(event)));
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        SV_MessageGlobal(PluginInstance.message_global_sound_path);
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        CL_OnConnect(event.client);
        SV_PlayerJoin(PluginInstance.player_join_sound_path);
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        CL_PlayerStart(PluginInstance.player_start_sound_path, event.client);
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        CL_OnDisconnect(event.client);
        SV_PlayerLeave(PluginInstance.player_leave_sound_path);
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SERVER_EMPTY:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        SV_EmptyAllClients();
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