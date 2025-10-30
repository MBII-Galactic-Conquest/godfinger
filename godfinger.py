# platform imports
import os
import re
import time
import json
import threading
import traceback
import io
import psutil
import logging
import argparse
import signal
import sys
import subprocess
import tempfile

IsVenv = sys.prefix != sys.base_prefix
if not IsVenv:
    print("ERROR : Running outside of virtual environment, run prepare.bat on windows or prepare.sh on unix, then come back")
    sys.exit()

Server = None

def Sighandler(signum, frame):
    if signum == signal.SIGINT or signum == signal.SIGTERM or signum == signal.SIGABRT:
        global Server
        if Server != None:
            Server.restartOnCrash = False
            Server.Stop()

# sys.platform() for more info
IsUnix = (os.name == "posix")
IsWindows = (os.name == "nt")

if IsUnix:
    signal.signal(signal.SIGINT, Sighandler)
    signal.signal(signal.SIGTERM, Sighandler)
    signal.signal(signal.SIGABRT, Sighandler)
elif IsWindows:
    signal.signal(signal.SIGINT, Sighandler)
    signal.signal(signal.SIGTERM, Sighandler)
    signal.signal(signal.SIGABRT, Sighandler)

Argparser = argparse.ArgumentParser(prog="Godfinger", description="The universal python platform for MBII server monitoring", epilog="It's a mess.")
Argparser.add_argument("-d", "--debug", action="store_true")
Argparser.add_argument("-lf", "--logfile")
Argparser.add_argument("-mbiicmd")
Args = Argparser.parse_args()

Log = logging.getLogger(__name__)

# custom imports
import lib.shared.config as config
import lib.shared.rcon as rcon
import lib.shared.serverdata as serverdata
import lib.shared.threadcontrol as threadcontrol
import godfingerEvent
import godfingerAPI
import lib.shared.client as client
import lib.shared.clientmanager as clientmanager
import lib.shared.pk3 as pk3
import queue
import database
import plugin
import lib.shared.teams as teams
import logMessage
import math
import lib.shared.colors as colors
import cvar
import godfingerinterface
import lib.shared.timeout as timeout

INVALID_ID = -1
USERINFO_LEN = len("userinfo: ")

CONFIG_DEFAULT_PATH = os.path.join(os.getcwd(),"godfingerCfg.json")
# Things like port and ip can be omitted in future, since this thing is supposed to be sharing the filesystem with the server, it could read it's config for credentials.
CONFIG_FALLBACK = \
"""{
    "Name":"MBII Godfinger : Consequetive Failure",
    "Remote":
    {
        "address":
        {
            "ip":"localhost",
            "port":29070
        },
        "bindAddress":"localhost",
        "password":"rconPassword"
    },

    "MBIIPath": "your/path/here/",
    "logFilename":"server.log",
    "serverPath":"your/path/here/",
    "serverFileName":"mbiided.x86.exe",
    "logicDelay":0.016,
    "restartOnCrash": false,

    "interfaces":
    {
        "pty":
        {
            "target":"path/to/your/mbiided.exe",
            "inputDelay":0.001
        },
        "rcon":
        {
            "Remote":
            {
                "address":
                {
                    "ip":"localhost",
                    "port":29070
                },
                "bindAddress":"localhost",
                "password":"fuckmylife"
            },
            "logFilename":"server.log",
            "logReadDelay":0.1,

            "Debug":
            {
                "TestRetrospect":false
            }
        }
    },
    "interface":"rcon",
    

    "paths":
    [
        "./"
    ],

    "prologueMessage":"Initialized Godfinger System",
    "epilogueMessage":"Finishing Godfinger System",

    "Plugins":
    [
        {
            "path":"plugins.shared.test.testPlugin"
        }
    ]

}
"""


class MBIIServer:

    STATUS_SERVER_JUST_AN_ERROR = -6
    STATUS_SERVER_NOT_RUNNING = -5
    STATUS_PLUGIN_ERROR = -4
    STATUS_RESOURCES_ERROR = -3
    STATUS_RCON_ERROR = -2
    STATUS_CONFIG_ERROR = -1
    STATUS_INIT = 0
    STATUS_RUNNING = 1
    STATUS_FINISHING = 2
    STATUS_FINISHED = 3
    STATUS_STOPPING = 4
    STATUS_STOPPED = 5

    @staticmethod
    def StatusString(statusId):
        if statusId == MBIIServer.STATUS_INIT:
            return "Status : Initialized Ok."
        elif statusId == MBIIServer.STATUS_CONFIG_ERROR:
            return "Status : Error at configuration load."
        else:
            return "Unknown status id." # implement later
    
    def ValidateConfig(self, cfg : config.Config) -> bool:
        if cfg == None:
            return False
        curVar = cfg.GetValue("MBIIPath", None)
        if curVar == None or curVar == "your/path/here/":
            return False
        curVar = cfg.GetValue("serverFileName", None)
        if curVar == None or curVar == "":
            return False
        curVar = cfg.GetValue("serverPath", None)
        if curVar == None or curVar == "your/path/here/":
            return False
        curVar = cfg.GetValue("interface", None)
        if curVar == None or ( curVar != "pty" and curVar != "rcon" ):
            return False
        elif curVar == "pty":
            Log.error("pty Interface is not fully implemented, use rcon instead.")
            return False
        return True


    def GetStatus(self):
        return self._status

    def __init__(self):
        self._isFinished = False
        self._isRunning = False
        self._isRestarting = False
        self._pluginManager = None
        self._svInterface = None
        self._gatheringExitData = False
        self._exitLogMessages = []

        startTime = time.time()
        self._status = MBIIServer.STATUS_INIT
        Log.info("Initializing Godfinger...")
        # Config load first
        self._config = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)
        if self._config == None:
            self._status = MBIIServer.STATUS_CONFIG_ERROR
            return
    
        if not self.ValidateConfig(self._config):
            self._status = MBIIServer.STATUS_CONFIG_ERROR
            return
    
        if "paths" in self._config.cfg:
            for path in self._config.cfg["paths"]:
                sys.path.append(os.path.normpath(path))
        
        Log.debug("System path total %s", str(sys.path))

        self._svInterface = None
        cfgIface = self._config.GetValue("interface", "pty")
        if cfgIface == "pty":
            self._svInterface = godfingerinterface.PtyInterface(cwd=self._config.cfg["serverPath"],\
                                                                args=[os.path.join(self._config.cfg["serverPath"], self._config.cfg["interfaces"]["pty"]["target"])]\
                                                                + (Args.mbiicmd.split() if Args.mbiicmd else []),\
                                                                inputDelay=self._config.cfg["interfaces"]["pty"]["inputDelay"],\
                                                                )
        elif cfgIface == "rcon":
            self._svInterface = godfingerinterface.RconInterface(   self._config.cfg["interfaces"]["rcon"]["Remote"]["address"]["ip"],\
                                                                    self._config.cfg["interfaces"]["rcon"]["Remote"]["address"]["port"],\
                                                                    self._config.cfg["interfaces"]["rcon"]["Remote"]["bindAddress"],\
                                                                    self._config.cfg["interfaces"]["rcon"]["Remote"]["password"],\
                                                                    os.path.join(self._config.cfg["MBIIPath"], self._config.cfg["interfaces"]["rcon"]["logFilename"]),\
                                                                    self._config.cfg["interfaces"]["rcon"]["logReadDelay"],
                                                                    self._config.cfg["interfaces"]["rcon"]["Debug"]["TestRetrospect"],
                                                                    procName=self._config.cfg["serverFileName"])
        
        if self._svInterface == None:
            Log.error("Server interface was not initialized properly.")
            self._status = MBIIServer.STATUS_CONFIG_ERROR
            return
    
        if IsWindows:
            try:
                os.system("title " + self._config.cfg["Name"])
            except Exception as e:
                Log.warning("Failed to set console title: %s", str(e))

        # Databases
        self._dbManager = database.DatabaseManager()
        r = self._dbManager.CreateDatabase("Godfinger.db", "Godfinger")
        self._database = self._dbManager.GetDatabase("Godfinger")
        self._database.Open()

        # Archives
        self._pk3Manager = pk3.Pk3Manager()
        self._pk3Manager.Initialize([self._config.cfg["MBIIPath"]])

        if not self._svInterface.Open():
            Log.error("Unable to Open server interface.")
            self._status = MBIIServer.STATUS_SERVER_JUST_AN_ERROR
            return
        self._svInterface.WaitUntilReady()
        
        # Cvars
        # Init at Start
        self._cvarManager = cvar.CvarManager(self._svInterface)
        
        # Client management
        self._clientManager = clientmanager.ClientManager()

        # Server data handling
        start_sd = time.time()
        exportAPI = godfingerAPI.API()
        exportAPI.GetClientCount    = self.API_GetClientCount
        exportAPI.GetClientById     = self.API_GetClientById
        exportAPI.GetClientByName   = self.API_GetClientByName
        exportAPI.GetAllClients     = self.API_GetAllClients
        exportAPI.GetCurrentMap     = self.API_GetCurrentMap
        exportAPI.GetServerVar      = self.API_GetServerVar
        exportAPI.CreateDatabase    = self.API_CreateDatabase
        exportAPI.AddDatabase       = self.API_AddDatabase
        exportAPI.GetDatabase       = self.API_GetDatabase
        exportAPI.GetPlugin         = self.API_GetPlugin
        exportAPI.Restart           = self.Restart
        self._serverData = serverdata.ServerData(self._pk3Manager, self._cvarManager, exportAPI, self._svInterface, Args)
        Log.info("Loaded server data in %s seconds." %(str(time.time() - start_sd)))


        # Technical
        # Plugins
        self._pluginManager = plugin.PluginManager()
        result = self._pluginManager.Initialize(self._config.cfg["Plugins"], self._serverData)
        if not result:
            self._status = MBIIServer.STATUS_PLUGIN_ERROR
            return
        self._logicDelayS = self._config.cfg["logicDelay"]
    
        self._isFinished = False
        self._isRunning = False
        self._isRestarting = False
        self._lastRestartTick = 0.0
        self._restartTimeout = timeout.Timeout()
        self.restartOnCrash = self._config.cfg["restartOnCrash"]
            

        Log.info("The Godfinger initialized in %.2f seconds!\n" %(time.time() - startTime))
    
    def Finish(self):
        # Ensure that finish is called only once; if _isFinished is already set, skip cleanup.
        if not hasattr(self, "_isFinished") or not self._isFinished:
            Log.info("Finishing Godfinger...")
            self._status = MBIIServer.STATUS_FINISHING
            self.Stop()
            # Only attempt to finish _pluginManager if it was successfully initialized.
            if self._pluginManager is not None:
                self._pluginManager.Finish()
            self._status = MBIIServer.STATUS_FINISHED
            self._isFinished = True
            Log.info("Finished Godfinger.")
    
    def __del__(self):
        self.Finish()
        # Safely delete attributes if they exist.
        if hasattr(self, "_pluginManager"):
            del self._pluginManager
            self._pluginManager = None
        if hasattr(self, "_svInterface"):
            del self._svInterface
            self._svInterface = None



    # status notrunc
    # hostname: MBII Test Server
    # version : 1.0.1.0 26
    # game    : MBII
    # udp/ip  : localhost:29070 os(Windows) type(public dedicated)
    # map    : mb2_smuggler gametype(7)
    # players : 0 humans, 0 bots (32 max)
    # uptime  : 0h0m16s
    # cl score ping name            address                                 rate
    # -- ----- ---- --------------- --------------------------------------- -----
    #  0     0   50 ^0^1C^0 ^72cwldys ^7                     127.0.0.1:20071 50000
    def _FetchStatus(self):
        statusStr = self._svInterface.Status()
        if statusStr != None:
            Log.debug(statusStr)
            splitted = statusStr.splitlines()
            versionSplit = splitted[2].split()
            version = versionSplit[2] + "_" + versionSplit[3]
            gameType = splitted[3].split()[2]
            mapLine = splitted[5]
            splittedMap = mapLine.split()
            mapName = splittedMap[2]
            mode    = int(splittedMap[3][splittedMap[3].find("(")+1:splittedMap[3].rfind(")")])
            Log.info("Version %s, GameType %s, Mapname %s, Mode %i" %(version, gameType, mapName, mode))
            self._serverData.version = version
            self._serverData.gameType = gameType
            self._serverData.mapName = mapName
            self._serverData.mode = mode
            l = len( splitted )
            if l > 10:
                for i in range (10, l):
                    line = splitted[i]
                    playerSplit = line.split()
                    if len(playerSplit) >= 6: # hardcode
                        addr = playerSplit[-2]
                        id = int(playerSplit[0])
                        extraName = len(playerSplit) - 6
                        name = playerSplit[3]
                        for i in range(extraName):
                            name += " " + playerSplit[4 + i]
                        if name[-2] == "^" and name[-1] == "7":
                            name = name[:-2].strip()
                        if name[0] == '(' and name[-1] == ')':
                            name = name[1:-1]   # strip only first and last '(' and ')' chars
                        Log.debug("Status client info addr %s, id %s, name \"%s\"" %(addr, id, name))
                        existing = self._clientManager.GetClientById(id)
                        if existing == None:
                            newClient = client.Client(id, name, addr)
                            self._clientManager.AddClient(newClient)
                        else:
                            if existing.GetName() != name:
                                existing._name = name
                            if existing.GetAddress() != addr:
                                existing._address = addr
            playersLine = splitted[6]
            startIndex = playersLine.find("(")
            endIndex = playersLine.find(" max")
            if startIndex != -1 and endIndex != -1:
                self._serverData.maxPlayers = int(playersLine[startIndex+1:endIndex])
                Log.debug("Status players max count %d"%self._serverData.maxPlayers)
            else:
                self._serverData.maxPlayers = 32
                Log.warning("Server status is having invalid format, setting default values to status data.")
        else:
            self._serverData.maxPlayers = 32
            Log.warning("Server status is unreachable, setting default values to status data.")
        pass

    
    def Restart(self, timeout = 60):
        if not self._isRestarting:
            self._isRestarting = True
            self._restartTimeout.Set(timeout)
            self._lastRestartTick = timeout
            self._svInterface.SvSay("^1 {text}.".format(text = "Godfinger Restarting procedure started, ETA %s"%self._restartTimeout.LeftDHMS()))
            Log.info("Restart issued, proceeding.")
    
    def Start(self):
        # a = 0/0
        try:
            # check for server process running first
            sv_fname = self._config.cfg["serverFileName"]
            if not sv_fname in (p.name() for p in psutil.process_iter()):
                self._status = MBIIServer.STATUS_SERVER_NOT_RUNNING
                if not Args.debug:
                    Log.error("Server is not running, start the server first, terminating...")
                    return
                else:
                    Log.debug("Running in debug mode and server is offline, consider server data invalid.")

            if not self._cvarManager.Initialize():
                Log.error("Failed to initialize CvarManager, abort startup.")
                self._status = MBIIServer.STATUS_SERVER_JUST_AN_ERROR
                return

            allCvars = self._cvarManager.GetAllCvars()
            Log.debug("All cvars %s" % str(allCvars))

            self._FetchStatus()

            if not self._pluginManager.Start():
                return
            self._isRunning = True
            self._status = MBIIServer.STATUS_RUNNING
            self._svInterface.SvSay("^1 {text}.".format(text = self._config.cfg["prologueMessage"]))
            while self._isRunning:
                startTime = time.time()
                self.Loop()
                elapsed = time.time() - startTime
                sleepTime = self._logicDelayS - elapsed
                if sleepTime <= 0:
                    sleepTime = 0
                time.sleep(sleepTime)

        except KeyboardInterrupt:
            s = signal.signal(signal.SIGINT, signal.SIG_IGN)
            Log.info("Interrupt recieved.")
            Sighandler(signal.SIGINT, -1)
            
    def Stop(self):
        if self._isRunning:
            Log.info("Stopping Godfinger...")
            self._svInterface.SvSay("^1 {text}.".format(text = self._config.cfg["epilogueMessage"]))
            self._status = MBIIServer.STATUS_STOPPING
            self._svInterface.Close()
            self._isRunning = False
            self._status = MBIIServer.STATUS_STOPPED
            Log.info("Stopped.") 

    def Loop(self):
        if self._isRestarting:
            if self._restartTimeout.IsSet():
                tick = self._restartTimeout.Left()
                if tick - self._lastRestartTick <= -5:
                    self._svInterface.SvSay("^1 {text}.".format(text = "Godfinger is about to restart in %s"%self._restartTimeout.LeftDHMS()))
                    self._lastRestartTick = tick
            else:
                Sighandler(signal.SIGINT, -1)
                self.restartOnCrash = False
                self.Stop()
                return
        messages = self._svInterface.GetMessages()
        while not messages.empty():
            message = messages.get()
            self._ParseMessage(message)
        self._pluginManager.Loop()

    def _ParseMessage(self, message : logMessage.LogMessage):
        
        line = message.content
        if line.startswith("ShutdownGame"):
            self.OnShutdownGame(message)
            return
    
        elif line.startswith("gsess"):
            self.OnRealInit(message)
            return
    
        # maybe its better to move it outside of string parsing
        if line.startswith("wd_"):
            if line == "wd_unavailable":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_UNAVAILABLE,None))
            elif line == "wd_existing":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_EXISTING,None))
            elif line == "wd_started":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_STARTED,None))
            elif line == "wd_died":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_DIED,None))
            elif line == "wd_restarted":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_RESTARTED,None))
            return

        lineParse = line.split()
        
        l = len(lineParse)
        # we shouldn't ever see blank lines in the server log if it isn't tampered with but just in case
        if l > 1:
            # first, because exit is a multi-line log entry, we have to do some stupid BS to record it
            if self._gatheringExitData:
                if lineParse[0].startswith("red:"):
                    self._exitLogMessages.append(message)
                elif lineParse[0] == "score:":
                    self._exitLogMessages.append(message)
                else:
                    # we've reached the end
                    self.OnExit(self._exitLogMessages)
                    self._exitLogMessages = []
                    self._gatheringExitData = False
            if lineParse[0] == "SMOD":  # Handle SMOD commands
                if lineParse[1] == "say:":      # smod server say (admin message)
                    pass
                elif lineParse[1] == "smsay:":   # smod chat smsay (admin-only chat message)
                    self.OnSmsay(message)
                elif lineParse[1] == "command":
                    self.OnSmodCommand(message)
            elif lineParse[0] == "Successful":
                self.OnSmodLogin(message)
            elif lineParse[1] == "say:":  # Handle say messages by players (not server)
                self.OnChatMessage(message)
            elif lineParse[1] == "sayteam:":
                self.OnChatMessageTeam(message)
            elif lineParse[0] == "Player":
                self.OnPlayer(message) # it's gonna be a long ride
            elif lineParse[0] == "Kill:":
                self.OnKill(message)
            elif lineParse[0] == "Exit:":
                self._gatheringExitData = True
                self._exitLogMessages.append(message)
            elif lineParse[0] == "ClientConnect:":
                self.OnClientConnect(message)
            elif lineParse[0] == "ClientBegin:":
                self.OnClientBegin(message)
            elif lineParse[0] == "InitGame:":
                self.OnInitGame(message)
            elif lineParse[0] == "ClientDisconnect:":
                self.OnClientDisconnect(message)
            elif lineParse[0] == "ClientUserinfoChanged:":
                self.OnClientUserInfoChanged(message)
            else:
                return

    def OnChatMessage(self, logMessage : logMessage.LogMessage):
        messageRaw = logMessage.content
        lineParse = messageRaw.split()
        senderId = int(lineParse[0].strip(":"))
        senderClient = self._clientManager.GetClientById(senderId)
        Log.debug("Chat message %s, from client %s" % (messageRaw, str(senderClient)) )

        # Split the raw message by the quote character
        parts = messageRaw.split("\"")

        # Check if the list has at least 2 parts (meaning there was at least one quote)
        if len(parts) > 1:
            # The chat message content is expected to be the second part (index 1)
            message : str = parts[1]
            if message.startswith("!"):
                cmdArgs = message[1:].split()
                if cmdArgs and cmdArgs[0] == "help":
                    # Handle help command directly
                    self.HandleChatHelp(senderClient, teams.TEAM_GLOBAL, cmdArgs)
                    return  # Don't pass to plugins
            self._pluginManager.Event( godfingerEvent.MessageEvent( senderClient, message, { 'messageRaw' : messageRaw }, isStartup = logMessage.isStartup ) )
        else:
            pass
            # Handle the malformed message (missing quotes)
            # Log.warning(f"Malformed chat message: missing quote characters. Skipping event. Raw: {messageRaw}")

    def OnChatMessageTeam(self, logMessage : logMessage.LogMessage):
        messageRaw = logMessage.content
        lineParse = messageRaw.split()
        senderId = int(lineParse[0].strip(":"))
        senderClient = self._clientManager.GetClientById(senderId)

        # Apply the same robust check for team chat
        parts = messageRaw.split("\"")
        if len(parts) > 1:
            message : str = parts[1]
            Log.debug("Team chat meassge %s, from client %s" % (messageRaw, str(senderClient)))
            self._pluginManager.Event( godfingerEvent.MessageEvent( senderClient, message, { 'messageRaw' : messageRaw }, senderClient.GetTeamId(), isStartup = logMessage.isStartup ) )
        else:
            pass
            # Log.warning(f"Malformed team chat message: missing quote characters. Skipping event. Raw: {messageRaw}")
    
    def OnPlayer(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("On Player log entry %s ", textified)

        # Initialize cl to None to prevent UnboundLocalError
        cl = None

        posUi = textified.find("u")
        if posUi != -1:
            ui = textified[posUi + USERINFO_LEN + 1 : len(textified)-1]
            pi = textified[0:posUi]
            splitted = pi.split()
            pidNum = int(splitted[1])
            cl = self._clientManager.GetClientById(pidNum)

            if cl != None:
                splitui = ui.split("\\")
                vars = {}
                changedOld = {}

                # FIX: Set the upper bound of the loop to be len(splitui) - 1
                # This ensures the loop always stops when the last valid key is reached
                # which leaves a safe index+1 for the corresponding value.
                # len(splitui) - 1 works for both odd and even lengths.
                for index in range (0, len(splitui) - 1, 2):
                    vars[splitui[index]] = splitui[index+1]
                with cl._lock:

                    newTeamId = cl.GetTeamId() # Default to current team to prevent unnecessary updates/crashes

                    if "team" in vars:
                        newTeamId = teams.TranslateTeam(vars["team"])
                    else:
                        Log.warning(f"OnPlayer event is missing 'team' variable for client ID {cl.GetId()}")

                    # Now proceed with the team change check using the safely determined newTeamId
                    if cl.GetTeamId() != newTeamId:
                        # client team changed
                        changedOld["team"] = cl.GetTeamId()
                        cl._teamId = newTeamId

                    if "name" in vars:
                        if cl.GetName() != vars["name"]:
                            changedOld["name"] = cl.GetName()
                            cl._name = vars["name"]

                    if "ja_guid" in vars:
                        if cl._jaguid != vars["ja_guid"]:
                            changedOld["ja_guid"] = cl._jaguid
                            cl._jaguid = vars["ja_guid"]
                if len(changedOld) > 0 :
                    self._pluginManager.Event( godfingerEvent.ClientChangedEvent(cl, changedOld, isStartup = logMessage.isStartup ) ) # a spawned client changed
                else:
                    self._pluginManager.Event( godfingerEvent.PlayerSpawnEvent ( cl, vars,  isStartup = logMessage.isStartup ) ) # a newly spawned client
            else:
                Log.warning("Client \"Player\" event with client is None.")

        # Only call PlayerEvent if cl was successfully retrieved
        if cl != None:
            self._pluginManager.Event( godfingerEvent.PlayerEvent(cl, {"text":textified}, isStartup = logMessage.isStartup))

    def HandleChatHelp(self, senderClient, teamId, cmdArgs):
        """Handle !help command for regular chat"""
        commandAliasList = self._serverData.GetServerVar("registeredCommands")
        if commandAliasList is None:
            commandAliasList = []
        
        if len(cmdArgs) > 1:
            # Looking for specific command help
            commandName = cmdArgs[1].lower()
            for commandAlias, helpText in commandAliasList:
                if commandName == commandAlias.lower():
                    self._svInterface.Say('^1[Godfinger]: ^7' + helpText)
                    return True
            # Command not found
            self._svInterface.Say(f"^1[Godfinger]:^7 Couldn't find chat command: {commandName}")
        else:
            # List all available commands
            commandStr = "Available commands (Say !help <command> for details): " + ', '.join([aliases for aliases, _ in commandAliasList])
            maxStrLen = 950
            if len(commandStr) > maxStrLen:
                messages = []
                # Break into batches for more efficient execution
                while len(commandStr) > maxStrLen:
                    splitIndex = commandStr.rfind(',', 0, maxStrLen)
                    if splitIndex == -1:
                        splitIndex = maxStrLen
                    msg = commandStr[:splitIndex]
                    commandStr = commandStr[splitIndex+1:].strip()
                    messages.append(msg)
                if len(commandStr) > 0:
                    messages.append(commandStr)
                self._svInterface.BatchExecute("b", [f"say {'^1[Godfinger]: ^7' + msg}" for msg in messages])
            else:
                self._svInterface.Say('^1[Godfinger]: ^7' + commandStr)
        
        return True

    def HandleSmodHelp(self, playerName, smodID, adminIP, cmdArgs):
        """Handle !help command for smod"""
        smodCommandAliasList = self._serverData.GetServerVar("registeredSmodCommands")
        if smodCommandAliasList is None:
            smodCommandAliasList = []
        
        if len(cmdArgs) > 1:
            # Looking for specific command help
            commandName = cmdArgs[1].lower()
            for commandAlias, helpText in smodCommandAliasList:
                if commandName == commandAlias.lower():
                    self._svInterface.SmSay(helpText)
                    return True
            # Command not found
            self._svInterface.SmSay(f"Couldn't find smod command: {commandName}")
        else:
            # List all available smod commands
            allCommands = ', '.join([aliases for aliases, _ in smodCommandAliasList])
            commandStr = "Smod commands: " + allCommands
            maxStrLen = 100
            if len(commandStr) > maxStrLen:
                messages = []
                # Break into batches for more efficient execution
                while len(commandStr) > maxStrLen:
                    splitIndex = commandStr.rfind(',', 0, maxStrLen)
                    if splitIndex == -1:
                        splitIndex = maxStrLen
                    msg = commandStr[:splitIndex]
                    commandStr = commandStr[splitIndex+1:].strip()
                    messages.append(msg)
                if len(commandStr) > 0:
                    messages.append(commandStr)
                self._svInterface.BatchExecute("b", [f"smsay {'^1[Godfinger]: ^7' + msg}" for msg in messages])
            else:
                self._svInterface.SmSay('^1[Godfinger]: ^7' + commandStr)
        return True

    def OnKill(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Kill log entry %s", textified)

        # Split the log message into parts using ': ' as the delimiter, limiting to 2 splits.
        # This results in a list of up to 3 parts (before ':', numeric part, message part).
        parts = textified.split(": ", 2)

        # Initialize variables to a safe state
        kill_part = ""
        numeric_part = ""
        message_part = ""

        # --- FIX: Safe Unpacking Logic ---
        if len(parts) >= 3:
            # Standard case: 3 or more parts found
            kill_part = parts[0]
            numeric_part = parts[1]
            # Rejoin the remaining parts in case there were extra ': ' delimiters in the message
            # Note: We rejoin with ': ' because that was the original split delimiter
            message_part = ": ".join(parts[2:])

        elif len(parts) == 2:
            # Fix: Handle the 'expected 3, got 2' case.
            # This means the numeric part (pids) is likely missing.
            # Log.warning(f"Malformed Kill message (expected 3 parts, got 2). Log: {textified}")
            kill_part = parts[0]
            numeric_part = ""
            message_part = parts[1]

        else:
            # Handle cases with 1 or 0 delimiters (severely malformed)
            # Log.error(f"Severely malformed Kill message (only {len(parts)} parts). Log: {textified}")
            return # Abort processing for invalid format
        # --- END FIX ---

        # Check if the numeric part (containing PIDs) was found/extracted
        if not numeric_part:
            Log.error(f"Kill message missing Player IDs. Log: {textified}")
            return # Cannot proceed without PIDs

        # Extract killer and victim player IDs
        pids = numeric_part.split()
        if len(pids) < 3:
            Log.error("Invalid kill log format (pids): %s", textified)
            return

        killer_pid = int(pids[0])
        victim_pid = int(pids[1])

        # Get client references
        cl = self._clientManager.GetClientById(killer_pid)
        clVictim = self._clientManager.GetClientById(victim_pid)
        if cl is None or clVictim is None:
            Log.debug(f"Player killed NPC, ignoring kill, full line: {textified}")
            return False

        tk_part = message_part.replace(cl.GetName(), "", 1).replace(clVictim.GetName(), "", 1).split()
        isTK = (tk_part[0] == "teamkilled")

        # Split the message part to isolate the kill details
        message_parts = message_part.split()
        if len(message_parts) < 4:
            Log.error("Invalid kill log format (message parts): %s", textified)
            return

        # Extract weapon info
        weapon_str = message_parts[-1]

        if cl is not None and clVictim is not None:
            if cl is clVictim:
                if weapon_str == "MOD_WENTSPECTATOR":
                    # Handle team change to spectator
                    old_team = cl.GetTeamId()
                    cl._teamId = teams.TEAM_SPEC
                    self._pluginManager.Event(godfingerEvent.ClientChangedEvent(cl, {"team": old_team}, logMessage.isStartup))
            self._pluginManager.Event(godfingerEvent.KillEvent(cl, clVictim, weapon_str, {"tk": isTK}, logMessage.isStartup))
        
    def OnExit(self, logMessages : list[logMessage.LogMessage]):
        textified = self._exitLogMessages[0].content
        textsplit = textified.split()
        Log.debug("Exit log entry %s", [x.content for x in logMessages])
        scoreLine = None
        playerScores = {}
        for m in logMessages:
            if m.content.startswith("red:"):
                scoreLine = m.content
            elif m.content.startswith("score:"):
                scoreParse = m.content.split()
                scorerName = ' '.join(scoreParse[6:])
                scorerScore = scoreParse[1]
                scorerPing = scoreParse[3]
                scorerClientID = scoreParse[5]
                playerScores[scorerClientID] = {"id" : scorerClientID, "name" : scorerName, "score" : scorerScore, "ping" : scorerPing}
        if scoreLine != None:
            scoreLine = scoreLine.strip()
            teamScores = dict(map(lambda a: a.split(":"), scoreLine.split()))
        else:
            scoreLine = "red:0 blue:0"
            teamScores = dict(map(lambda a: a.split(":"), scoreLine.split()))
        exitReason = ' '.join(textsplit[1:])
        self._pluginManager.Event( godfingerEvent.ExitEvent( {"reason" : exitReason, "teamScores" : teamScores, "playerScores" : playerScores}, isStartup = self._exitLogMessages[0].isStartup ) )


    def OnClientConnect(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Client connect log entry %s", textified)
        lineParse = textified.split()
        extraName = len(lineParse) - 6
        token_to_check = lineParse[3 + extraName]

        try:
            # 1. Strip color codes (e.g., '^6'), which might be mistaken for part of a number.
            #    The 'colors' utility is imported in godfingerinterface and assumed available here.
            stripped_token = colors.StripColorCodes(token_to_check)

            # 2. Strip surrounding punctuation (like '(', ')') and whitespace.
            cleaned_token = stripped_token.strip("()").strip()

            # 3. Safely convert the cleaned token to an integer.
            id = int(cleaned_token)

        except ValueError:
            # If the token is still not a valid integerhandle gracefully.
            # Log.warning(f"OnClientConnect: Malformed ID token '{token_to_check}' encountered. Falling back to lineParse[1] for client ID.")

            # Fallback: Attempt to use the client ID from the known primary position (index 1).
            try:
                id = int(lineParse[1])
            except (ValueError, IndexError):
                # If all parsing fails, set a sentinel value that can be handled downstream.
                id = -1
        ip = lineParse[-1].strip(")")
        name = lineParse[1]
        for i in range(extraName):
            name += " " + lineParse[2 + i]
        if name[0] == '(' and name[-1] == ')':
            name = name[1:-1]   # strip only first and last '(' and ')' chars
        Log.debug("Client info parsed: ID: %s; IP: %s; Name: %s", str(id), ip, name )
        if not id in [cl.GetId() for cl in self.API_GetAllClients()]:
            newClient = client.Client(id, name, ip)
            self._clientManager.AddClient(newClient) # make sure its added BEFORE events are processed
            self._pluginManager.Event( godfingerEvent.ClientConnectEvent( newClient, None, isStartup = logMessage.isStartup ) )
        else:
            #Log.warning(f"Duplicate client with ID {id} connected, ignoring")
            pass

    def OnClientBegin(self, logMessage : logMessage.LogMessage ):
        textified = logMessage.content
        lineParse = textified.split()
        clientId = int(lineParse[1])
        client = self._clientManager.GetClientById(clientId)
        if client != None:
            pass
            self._pluginManager.Event( godfingerEvent.ClientBeginEvent( client, {}, isStartup = logMessage.isStartup ) )
    
    def OnClientDisconnect(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Client disconnect log entry %s", textified) 
        lineParse = textified.split()
        dcId = int(lineParse[1])
        cl = self._clientManager.GetClientById(dcId)
        if cl != None:
            Log.debug("Player with dcId %s disconnected ", str(dcId))
            self._pluginManager.Event( godfingerEvent.ClientDisconnectEvent( cl, None, isStartup = logMessage.isStartup ) )
            self._clientManager.RemoveClient(cl) # make sure its removed AFTER events are processed by plugins
            if self._clientManager.GetClientCount() == 0:
                Log.debug("All players have left the server")
                self._pluginManager.Event( godfingerEvent.ServerEmptyEvent(isStartup = logMessage.isStartup))
        else:
            pass # player reconnected ( thats how server shits in logs for some reason)

    def OnClientUserInfoChanged(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Client user info changed log entry %s", textified)
        lineParse = textified.split()
        clientId = int(lineParse[1])
        userInfo = textified[23 + len(lineParse[1]):].strip()  # easier if we just ignore everything up until the variables
        cl = self._clientManager.GetClientById(clientId)
        if cl != None:
            cl.Update(userInfo)
            self._pluginManager.Event( godfingerEvent.ClientChangedEvent( cl, cl.GetInfo(), isStartup = logMessage.isStartup ) )
        else:
            Log.warning(f"Attempted to update userinfo of client {clientId} which does not exist, ignoring")

    def OnInitGame(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Init game log entry %s", textified)
        configStr = textified[len("InitGame: \\"):len(textified)]
        vars = {}
        splitted = configStr.split("\\")
        for index in range (0, len(splitted) - 1, 2):
            vars[splitted[index]] = splitted[index+1]
            
        if "mapname" in vars:
            if vars["mapname"] != self._serverData.mapName:
                print("mapname cvar parsed, applying " + vars["mapname"] + " : " + self._serverData.mapName)
                if self._serverData.mapName != '':          # ignore first map ;
                    self.OnMapChange(vars["mapname"], self._serverData.mapName)
                self._serverData.mapName = vars["mapname"]
        else:
            self._serverData.mapName = self._svInterface.GetCurrentMap()
        
        Log.info("Current map name on init : %s", self._serverData.mapName)
        
        self._pluginManager.Event( godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_INIT, { "vars" : vars }, isStartup = logMessage.isStartup ) )
        self._pluginManager.Event( godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT, {}, isStartup = logMessage.isStartup ) )

    def OnShutdownGame(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Shutdown game log entry %s", textified)
        allClients = self._clientManager.GetAllClients()
        for client in allClients:
            Log.debug("Shutdown pseudo-disconnecting client %s" %str(client))
        
        self._pluginManager.Event( godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN, None, isStartup = logMessage.isStartup ) )
    
    def OnRealInit(self, logMessage : logMessage.LogMessage):
        Log.debug("Server starting up for real.")
        self._pluginManager.Event(godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT, None, isStartup = logMessage.isStartup ))

    def OnMapChange(self, mapName : str, oldMapName : str):
        Log.debug(f"Map change event received: {mapName}")
        self._pluginManager.Event(godfingerEvent.MapChangeEvent(mapName, oldMapName))

    def OnSmsay(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug(f"Smod say event received: {textified}")
        lineSplit = textified.split()

        # Check if the token '(adminID:' is present in the list before trying to get its index.
        # This prevents the ValueError.
        if '(adminID:' in lineSplit:
            adminIDIndex = lineSplit.index('(adminID:')
            smodID = lineSplit[adminIDIndex + 1].strip(")")
            senderName = ' '.join(lineSplit[2:adminIDIndex])
            senderIP = lineSplit[adminIDIndex + 3].strip("):")
            message = ' '.join(lineSplit[adminIDIndex + 4:])
            messageLower = message.lower()
            cmdArgs = messageLower.split()
            if cmdArgs and cmdArgs[0].startswith("!"):
                command = cmdArgs[0][1:]  # Remove the !
                if command == "help":
                    self.HandleSmodHelp(senderName, smodID, senderIP, cmdArgs)
                    return True  # Command handled, don't pass to plugins
            self._pluginManager.Event(godfingerEvent.SmodSayEvent(senderName, int(smodID), senderIP, message, isStartup = logMessage.isStartup))
        else:
            # Handle the malformed message: log a warning and skip processing the event
            pass

    def OnSmodCommand(self, logMessage : logMessage.LogMessage):
        Log.debug(f"SmodCommand change event received: {logMessage.content}")
        data = {}
        log_message = logMessage.content
        data = {
            'smod_name': None,
            'smod_id': None,
            'smod_ip': None,
            'command': None,
            'target_name': None,
            'target_id': None,
            'target_ip': None
        }

        # Split the message into parts based on the command structure
        parts = log_message.split(' executed by ')
        
        # Parse SMOD executor information
        if len(parts) >= 2:
            # Extract SMOD details from first part
            smod_info = parts[1].split(' (IP: ')
            if len(smod_info) == 2:
                # Extract name and admin ID
                name_part = smod_info[0]
                match = re.search(r'^(?:\^?\d+)?(.+?)\((adminID: (\d+))\)$', name_part)
                if match:
                    data['smod_name'] = match.group(1).strip()
                    data['smod_id'] = match.group(3)
                    data['smod_ip'] = smod_info[1].split(')')[0]
            
            # Extract command information
            command_part = parts[0].split(' (')
            if len(command_part) >= 1:
                command_match = re.search(r'SMOD command \((.*)\) executed', log_message)
                if command_match:
                    data['command'] = command_match.group(1).lower()
        
        # Check for target information
        if ' against ' in log_message:
            target_part = log_message.split(' against ')[1]
            target_info = target_part.split(' (IP: ')[0]
            target_match = re.search(r'^(?:\^?\d+)?(.+?)\((IP: .+?)\)$', target_part)
            if target_match:
                data['target_name'] = target_match.group(1).strip()
                data['target_ip'] = target_match.group(2).split(':')[0]
                
                # Try to extract target ID if present
                id_match = re.search(r'\((\d+)\)', target_info)
                if id_match:
                    data['target_id'] = id_match.group(1)
        self._pluginManager.Event(godfingerEvent.SmodCommandEvent(data))

    def OnSmodLogin(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug(f"Smod login event received: {textified}")

        data = {
            'smod_name': None,
            'smod_id': None,
            'smod_ip': None
        }

        # Parse the login message
        # Expected format: "Successful SMOD login by <name>(adminID: <id>) (IP: <ip>:<port>)"
        if 'adminID:' in textified and 'IP:' in textified:
            # Split by '(adminID:' to separate name from the rest
            parts = textified.split('(adminID:')
            if len(parts) >= 2:
                # Extract name - it's between "by " and "(adminID:"
                name_part = parts[0].replace('Successful SMOD login by ', '').strip()
                data['smod_name'] = name_part

                # Extract admin ID and IP from the second part
                remaining = parts[1]

                # Extract admin ID (between start and next ')')
                id_match = re.search(r'^(\d+)\)', remaining)
                if id_match:
                    data['smod_id'] = id_match.group(1)

                # Extract IP (between 'IP: ' and ')')
                ip_match = re.search(r'IP:\s*([^)]+)\)', remaining)
                if ip_match:
                    # Strip port if present (everything after ':')
                    ip_with_port = ip_match.group(1)
                    data['smod_ip'] = ip_with_port.split(':')[0]

        self._pluginManager.Event(godfingerEvent.SmodLoginEvent(data['smod_name'], data['smod_id'], data['smod_ip'], isStartup = logMessage.isStartup))

    # API export functions 
    def API_GetClientById(self, id):
        return self._clientManager.GetClientById(id)

    def API_GetClientByName(self, name):
        return self._clientManager.GetClientByName(name)

    def API_GetAllClients(self):
        return self._clientManager.GetAllClients()

    def API_GetClientCount(self):
        return self._clientManager.GetClientCount()

    def API_GetCurrentMap(self):
        return "" + self._serverData.mapName

    def API_GetServerVar(self, var):
        return self._serverData.GetServerVar(var)

    def API_SetServerVar(self, var, val):
        self._serverData.SetServerVar(var, val)

    def API_CreateDatabase(self, path, name) -> int:
        return self._dbManager.CreateDatabase(path, name)

    def API_AddDatabase(self, db : database.ADatabase) -> int:
        return self._dbManager.AddDatabase(db)
    
    def API_GetDatabase(self, name) -> database.ADatabase:
        return self._dbManager.GetDatabase(name)

    def API_GetPlugin(self, name) -> plugin.Plugin:
        return self._pluginManager.GetPlugin(name)

    def API_Restart(self, timeout = 60):
        self.Restart(timeout)

    def IsRestarting(self) -> bool:
        return self._isRestarting

def InitLogger():
    loggingMode = logging.INFO
    loggingFile = ""

    if Args.debug:
        print("DEBUGGING MODE.")
        loggingMode = logging.DEBUG
    if Args.logfile:
        # Add timestamp to log file so they don't get overwritten
        if os.path.exists(Args.logfile):
            newLogfile = Args.logfile + '-' + time.strftime("%m%d%Y_%H%M%S", time.localtime(time.time()))
            Args.logfile = newLogfile
        else:
            newLogfile = Args.logfile
        print(f"Logging into file {newLogfile}")
        loggingFile = newLogfile
    
    if loggingFile != "":
        logging.basicConfig(
        filename = loggingFile,
        level = loggingMode,
        filemode = 'a',
        format='%(asctime)s %(levelname)08s %(name)s %(message)s',
        )
    else:
        logging.basicConfig(
        level = loggingMode,
        filemode = 'a',
        format='%(asctime)s %(levelname)08s %(name)s %(message)s',
        )

def main():
    InitLogger()
    Log.info("Godfinger entry point.")
    global Server
    Server = MBIIServer()
    int_status = Server.GetStatus()
    runAgain = True
    if int_status == MBIIServer.STATUS_INIT:
        while runAgain:
            try:
                runAgain = False
                Server.Start()  # it will exit the Start on user shutdown
            except Exception as e:
                Log.error(f"ERROR occurred: Type: {type(e)}; Reason: {e}; Traceback: {traceback.format_exc()}")
                try:
                    with open('lib/other/gf.txt', 'r') as file:
                        gf = file.read()
                        print("\n\n" + gf)
                        file.close()
                except Exception as e:
                    Log.error(f"ERROR occurred: No fucking god finger.txt")
                print("\n\nCRASH DETECTED, CHECK LOGS")
                Server.Finish()
                if Server.restartOnCrash:
                    runAgain = True
                    Server = MBIIServer()
                    int_status = Server.GetStatus()
                    if int_status == MBIIServer.STATUS_INIT:
                        continue  # start new server instance
                    else:
                        break
        int_status = Server.GetStatus()
        if int_status == MBIIServer.STATUS_SERVER_NOT_RUNNING:
            print("Unable to start with not running server for safety measures, abort init.")
        Server.Finish()
        if Server.IsRestarting():
            del Server
            Server = None
            cmd = (" ".join( sys.argv ) )
            dir = os.path.dirname(__file__)
            cmd = os.path.normpath(os.path.join(dir, cmd))
            cmd = (sys.executable + " " + cmd )
            
            # Cross-platform subprocess handling
            if IsWindows:
                subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                # Unix/Linux compatible detached process
                subprocess.Popen(cmd, shell=True, stdin=None, stdout=None, stderr=None, close_fds=True, 
                               start_new_session=True)
            sys.exit()
        del Server
        Server = None
    else:
        Log.info("Godfinger initialize error %s" % (MBIIServer.StatusString(int_status)))
    
    Log.info("The final gunshot was an exclamation mark on everything that had led to this point. I released my finger from the trigger, and it was over.")


if __name__ == "__main__":
    main()
