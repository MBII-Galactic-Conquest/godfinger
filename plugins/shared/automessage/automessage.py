
import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import os;
import lib.shared.config as config;
import threading;
import lib.shared.threadcontrol as threadcontrol;
import time;
import random;
import lib.shared.teams as teams;

SERVER_DATA = None;

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "automessageCfg.json");
CONFIG_FALLBACK = \
"""{
    "prefix":"^5[AutoMessage] ^7",
    "interval": 5,
    "allowLastMessageTwice" : false,
    "messages": [
        "Message 1",
        "Message 2",
        "Message 3",
        "Message 4",
        "Message 5"
    ]
}
"""
global AutomessageConfig;
AutomessageConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__);

PluginInstance = None;

class Automessage():
    def __init__(self, serverData : serverdata.ServerData):
        self._serverData = serverData;
        self.config = AutomessageConfig;
        self._threadLock = threading.Lock();
        self._threadControl = threadcontrol.ThreadControl();
        self._thread = threading.Thread(target=self._main_thread, daemon=True, args=(self._threadControl, self.config.cfg["interval"]));
        self._allowLastMessageTwice = self.config.cfg["allowLastMessageTwice"]
        self._lastMessage = ""
        self._silenced_players = {}

        self._commandList = {
            teams.TEAM_GLOBAL: {
                tuple(["muteautomessage", "muteam"]): ("!muteautomessage - Toggle AutoMessage visibility", self.HandleSilenceCommand)
            },
            teams.TEAM_EVIL: {
            },
            teams.TEAM_GOOD: {
            },
            teams.TEAM_SPEC: {
            }
        }

    def Start(self) -> bool:
        self._thread.start();
        return True;

    def Finish(self):
        with self._threadLock:
            self._threadControl.stop = True;
    
    def SendAutoMessage(self):
        messages = self.config.cfg['messages']
        if len(messages) == 0:
            message = "Error: No messages configured in automessageCfg.json"
        elif len(messages) == 1:
            message = messages[0]
        else:
            message = random.choice(messages)
            if not self._allowLastMessageTwice:
                while message == self._lastMessage:
                    message = random.choice(messages)
        self._lastMessage = message
        
        if self._serverData.is_extended:
            if not self._silenced_players:
                self._serverData.interface.SvPrint(self.config.cfg["prefix"] + message, "all")
            else:
                target_ids = []
                for cl in self._serverData.API.GetAllClients():
                    if cl.GetId() not in self._silenced_players:
                        target_ids.append(str(cl.GetId()))
                if not target_ids:
                    return
                target_str = ",".join(target_ids)
                self._serverData.interface.SvPrint(self.config.cfg["prefix"] + message, target_str)
        else:
            self._serverData.interface.SvSay(self.config.cfg["prefix"] + message);

    def HandleSilenceCommand(self, eventClient, teamId, cmdArgs):
        if not self._serverData.is_extended:
            self._serverData.interface.SvTell(eventClient.GetId(), "^1Error: ^7Server is not extended, this feature is unavailable.")
            return True
        
        client_id = eventClient.GetId()
        if client_id in self._silenced_players:
            del self._silenced_players[client_id]
            self._serverData.interface.SvTell(client_id, "You are no longer silencing the server.")
        else:
            self._silenced_players[client_id] = True
            self._serverData.interface.SvTell(client_id, "You are now silencing the server.")
            
        return True

    def OnClientDisconnect(self, client):
        client_id = client.GetId()
        if client_id in self._silenced_players:
            del self._silenced_players[client_id]

    def _main_thread(self, control, interval):
        while(True):
            stop = False;
            with self._threadLock:
                stop = control.stop;
            if stop == True:
                break;
            self.SendAutoMessage();
            time.sleep(interval);

    def HandleChatCommand(self, eventClient, teamId, cmdArgs) -> bool:
        command = cmdArgs[0].lower()
        if command.startswith("!"):
            command = command[1:]

        if teamId in self._commandList:
            for c in self._commandList[teamId]:
                if command in c:
                    return self._commandList[teamId][c][1](eventClient, teamId, cmdArgs)
        return False

    def OnChatMessage(self, eventClient, message: str, teamId: int) -> bool:
        if eventClient is None:
            return False

        if message.startswith("!"):
            message = message[1:]
            if len(message) > 0:
                cmdArgs = message.split()
                return self.HandleChatCommand(eventClient, teamId, cmdArgs)
        return False

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
    global PluginInstance;
    PluginInstance = Automessage(serverData);
    if exports != None:
        pass;

    newCommands = []
    rChatCommands = SERVER_DATA.GetServerVar("registeredCommands")
    if rChatCommands is not None:
        newCommands.extend(rChatCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for alias in cmd:
            if not alias.isdecimal():
                newCommands.append((alias, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newCommands)

    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance;
    return PluginInstance.Start();

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    global PluginInstance;
    PluginInstance.Finish();

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return PluginInstance.OnChatMessage(event.client, event.message, event.teamId)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        PluginInstance.OnClientDisconnect(event.client)
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

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()