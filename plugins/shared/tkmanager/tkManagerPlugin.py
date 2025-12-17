# TK Points Manager Plugin
# By ACHUTA
# Created for Godfinger Movie Battles II Scripting Platform created by ACHUTA and ViceDice

import logging
import json
import os
from time import time;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.teams as teams
import lib.shared.colors as colors

SERVER_DATA = None;
AUTOMARKTK_DURATION = 60 # minutes
IP_LIST_FILE = "automarktk_ips.json"

Log = logging.getLogger(__name__);

class TKManagerPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData = serverData
        self.target_port = getattr(serverData, 'config', {}).get('portFilter')
        self._messagePrefix = colors.ColorizeText("[TK]", "orange") + ": "
        self._commandList = \
            {
                # commands and aliases must be tuples because lists are unhashable apparently
                # index 0 : tuple of aliases for each command
                # index 1: tuple of help string and handler function
                teams.TEAM_GLOBAL : {
                },
                teams.TEAM_EVIL : {
                },
                teams.TEAM_GOOD : {
                },
                teams.TEAM_SPEC : {
                }
            }
        self._smodCommandList = \
            {
                # same as above
                tuple(["rtk", "resettk"]) : ("!<rtk | resettk> - reset tk points of all players", self.HandleResetTK),
                tuple(["automarktk"]) : ("!automarktk <name_substr> - auto-marktk player and add IP to list", self.HandleAutoMarkTk)
            }
        self._ipList = []
        self._ipListPath = os.path.join(os.path.dirname(__file__), IP_LIST_FILE)
        self.LoadIpList()

    def _get_interface(self):
        # Look up the specific interface for our port from the map we built in godfinger.py
        if hasattr(self._serverData, 'interfaceMap') and hasattr(self, 'target_port'):
            if self.target_port:
                return self._serverData.interfaceMap.get(int(self.target_port))
        return self._serverData.interface    

    def HandleResetTK(self, playerName, smodID, adminIP, messageParse):
        self._serverData.interface.ExecVstr("clearTK")
        return True

    def HandleSmodCommand(self, playerName, smodId, adminIP, cmdArgs):
        command = cmdArgs[0]
        if command.startswith("!"):
            # TODO: Make this an actual config option
            if command.startswith("!"):
                command = command[len("!"):]
        for c in self._smodCommandList:
            if command in c:
                return self._smodCommandList[c][1](playerName, smodId, adminIP, cmdArgs)
        return False

    def LoadIpList(self):
        if os.path.exists(self._ipListPath):
            try:
                with open(self._ipListPath, 'r') as f:
                    self._ipList = json.load(f)
            except Exception as e:
                Log.error(f"Failed to load IP list: {e}")
                self._ipList = []

    def SaveIpList(self):
        try:
            with open(self._ipListPath, 'w') as f:
                json.dump(self._ipList, f, indent=4)
        except Exception as e:
            Log.error(f"Failed to save IP list: {e}")

    def HandleAutoMarkTk(self, playerName, smodID, adminIP, cmdArgs):
        if len(cmdArgs) < 2:
            self._get_interface().SmSay(self._messagePrefix + "Usage: !automarktk <name_substring>")
            return True
        
        targetName = " ".join(cmdArgs[1:]).lower()
        matchingPlayers = []
        
        for client in self._serverData.API.GetAllClients():
            if targetName in colors.StripColorCodes(client.GetName()).lower():
                matchingPlayers.append(client)
        
        if len(matchingPlayers) == 0:
            self._get_interface().SmSay(self._messagePrefix + f"No players found matching '{targetName}'.")
            return True
        elif len(matchingPlayers) > 1:
            names = ", ".join([p.GetName() for p in matchingPlayers])
            self._get_interface().SmSay(self._messagePrefix + f"Multiple matches found: {names}. Please be more specific.")
            return True
        
        targetPlayer = matchingPlayers[0]
        targetIp = targetPlayer.GetIp()
        
        # MarkTK the player immediately
        self._get_interface().MarkTK(targetPlayer.GetId(), AUTOMARKTK_DURATION)
        
        # Add IP to list if not already present
        if targetIp not in self._ipList:
            self._ipList.append(targetIp)
            self.SaveIpList()
            self._get_interface().SmSay(self._messagePrefix + f"Auto-marked {targetPlayer.GetName()}^7 and added IP {targetIp} to list.")
        else:
            self._get_interface().SmSay(self._messagePrefix + f"Auto-marked {targetPlayer.GetName()}^7. IP {targetIp} was already in list.")
            
        return True

    def OnClientConnect(self, client):
        clientIp = client.GetIp()
        if clientIp in self._ipList:
            Log.info(f"Auto-marking TK for {client.GetName()} (IP {clientIp} in ban list)")
            self._get_interface().MarkTK(client.GetId(), AUTOMARKTK_DURATION)
            self._get_interface().SmSay(self._messagePrefix + f"Auto-marked {client.GetName()}^7 for {AUTOMARKTK_DURATION} minutes (IP Match).")

    def OnSmsay(self, playerName, smodID, adminIP, message):
        message = message.lower()
        messageParse = message.split()
        return self.HandleSmodCommand(playerName, smodID, adminIP, messageParse)

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
    PluginInstance = TKManagerPlugin(serverData)
    
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newVal)
    
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredSmodCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._smodCommandList:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._smodCommandList[cmd][0]))
    SERVER_DATA.SetServerVar("registeredSmodCommands", newVal)
    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    startTime = time()
    resetTKVstr = r'"settk 0 0;wait 1;settk 1 0;wait 1;settk 2 0;wait 1;settk 3 0;settk 4 0;wait 1;settk 5 0;wait 1;settk 6 0;settk 7 0;wait 1;settk 8 0;wait 9;settk 10 0;wait 1;settk 11 0;settk 12 0;wait 1;settk 13 0;wait 1;settk 14 0;settk 15 0;wait 1;settk 16 0;wait 1;settk 17 0;wait 1;settk 18 0;settk 19 0;wait 1;settk 20 0;wait 1;settk 21 0;settk 22 0;wait 1;settk 23 0;wait 1;settk 24 0;wait 1;settk 25 0;settk 26 0;wait 1;settk 27 0;wait 1;settk 28 0;settk 29 0;wait 1;settk 30 0;wait 1;settk 31 0"'
    PluginInstance._get_interface().SetVstr('clearTK', resetTKVstr)
    for i in PluginInstance._serverData.API.GetAllClients():
        PluginInstance.OnClientConnect(i)
    loadTime = time() - startTime
    # PluginInstance._get_interface.Say(PluginInstance._messagePrefix + f"TK Manager started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance;
    if not PluginInstance:
        return False;

    # ADD THIS: Safety check and Port Filtering
    if event.data is None or not isinstance(event.data, dict):
        pass 
    else:
        event_port = event.data.get('source_port')
        target = getattr(PluginInstance, 'target_port', None)
        
        # If the port doesn't match our filter, ignore the event
        if target and event_port and int(event_port) != int(target):
            return False

    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        PluginInstance.OnClientConnect(event.client)
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
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
        return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)
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