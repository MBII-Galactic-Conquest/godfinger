# TK Points Manager Plugin
# By ACHUTA
# Created for Godfinger Movie Battles II Scripting Platform created by ACHUTA and ViceDice

import logging
from time import time;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.teams as teams
import lib.shared.colors as colors

SERVER_DATA = None;

Log = logging.getLogger(__name__);

class TKManagerPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData = serverData
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
                tuple(["rtk", "resettk"]) : ("!<rtk | resettk> - reset tk points of all players", self.HandleResetTK)
            }

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
    resetTKVstr = '"settk 0 0;wait 1;settk 1 0;wait 1;settk 2 0;wait 1;settk 3 0;settk 4 0;wait 1;settk 5 0;wait 1;settk 6 0;settk 7 0;wait 1;settk 8 0;wait 9;settk 10 0;wait 1;settk 11 0;settk 12 0;wait 1;settk 13 0;wait 1;settk 14 0;settk 15 0;wait 1;settk 16 0;wait 1;settk 17 0;wait 1;settk 18 0;settk 19 0;wait 1;settk 20 0;wait 1;settk 21 0;settk 22 0;wait 1;settk 23 0;wait 1;settk 24 0;wait 1;settk 25 0;settk 26 0;wait 1;settk 27 0;wait 1;settk 28 0;settk 29 0;wait 1;settk 30 0;wait 1;settk 31 0"'
    PluginInstance._serverData.interface.SetVstr('clearTK', resetTKVstr)
    loadTime = time() - startTime
    # PluginInstance._serverData.interface.Say(PluginInstance._messagePrefix + f"TK Manager started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
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