
# platform imports
import os;
import time;
import json;
import threading;
import traceback;
import io;
import psutil;
import logging;
import argparse;
import signal;
import sys;
import subprocess;
import tempfile;

IsVenv = sys.prefix != sys.base_prefix;
if not IsVenv:
    print("ERROR : Running outside of virtual environment, run prepare.bat on windows or prepare.sh on unix, then come back");
    sys.exit();

Server = None;

def Sighandler(signum, frame):
    if signum == signal.SIGINT or signum == signal.SIGTERM or signal == signal.SIGABRT:
        global Server;
        if Server != None:
            Server.restartOnCrash = False;
            Server.Stop();

# sys.platform() for more info
IsUnix      = (os.name == "posix");
IsWindows   = (os.name == "nt");
if IsUnix:
    signal.signal(signal.SIGINT, Sighandler);
    signal.signal(signal.SIGTERM, Sighandler);
    signal.signal(signal.SIGABRT, Sighandler);
elif os.name == "nt":
    print("Windows specific stuff is not implemented, but it should be fine.");
    #import win32api; # requires pywin32
    #win32api.SetConsoleCtrlHandler(on_exit, True)

Argparser = argparse.ArgumentParser(prog="Godfinger", description="The universal python platform for MBII server monitoring", epilog="It's a mess.")
#Argparser.add_argument("DEBUG", help="Debugging mode.", type=int)
# parser.add_argument('filename')           # positional argument
# parser.add_argument('-c', '--count')      # option that takes a value
# parser.add_argument('-v', '--verbose',
#                     action='store_true')  # on/off flag
Argparser.add_argument("-d", "--debug", action="store_true");
Argparser.add_argument("-lf", "--logfile");
Argparser.add_argument("-mbiicmd");
Args = Argparser.parse_args();

Log = logging.getLogger(__name__);

# custom imports
import lib.shared.config as config;
import lib.shared.rcon as rcon;
import lib.shared.serverdata as serverdata;
import lib.shared.threadcontrol as threadcontrol;
import godfingerEvent;
import godfingerAPI;
import lib.shared.client as client;
import lib.shared.clientmanager as clientmanager;
import lib.shared.pk3 as pk3;
import queue;
import database;
import plugin;
import lib.shared.teams as teams;
import logMessage;
import math;
import lib.shared.colors as colors;
import cvar;
import godfingerinterface;
import lib.shared.timeout as timeout;

INVALID_ID = -1;
USERINFO_LEN = len("userinfo: ");

CONFIG_DEFAULT_PATH = os.path.join(os.getcwd(),"godfingerCfg.json");
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

    STATUS_SERVER_JUST_AN_ERROR = -6;
    STATUS_SERVER_NOT_RUNNING = -5;
    STATUS_PLUGIN_ERROR = -4;
    STATUS_RESOURCES_ERROR = -3;
    STATUS_RCON_ERROR = -2;
    STATUS_CONFIG_ERROR = -1;
    STATUS_INIT = 0;
    STATUS_RUNNING = 1;
    STATUS_FINISHING = 2;
    STATUS_FINISHED = 3;
    STATUS_STOPPING = 4;
    STATUS_STOPPED = 5;

    @staticmethod
    def StatusString(statusId):
        if statusId == MBIIServer.STATUS_INIT:
            return "Status : Initialized Ok.";
        elif statusId == MBIIServer.STATUS_CONFIG_ERROR:
            return "Status : Error at configuration load.";
        else:
            return "Unknown status id."; # implement later
    
    def ValidateConfig(self, cfg : config.Config) -> bool:
        if cfg == None:
            return False;
        curVar = cfg.GetValue("MBIIPath", None);
        if curVar == None or curVar == "your/path/here/":
            return False;
        curVar = cfg.GetValue("serverFileName", None);
        if curVar == None or curVar == "":
            return False;
        curVar = cfg.GetValue("serverPath", None);
        if curVar == None or curVar == "your/path/here/":
            return False;
        curVar = cfg.GetValue("interface", None);
        if curVar == None or ( curVar != "pty" and curVar != "rcon" ):
            return False;
        elif curVar == "pty":
            Log.error("pty Interface is not fully implemented, use rcon instead.");
            return False;
        return True;


    def GetStatus(self):
        return self._status;

    def __init__(self):
        self._isFinished = False
        self._isRunning = False
        self._isRestarting = False
        self._pluginManager = None
        self._svInterface = None

        startTime = time.time();
        self._status = MBIIServer.STATUS_INIT;
        Log.info("Initializing Godfinger...");
        # Config load first
        self._config = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)
        if self._config == None:
            # # handle config-less init
            # Log.error("Missing config.json, creating a fallback one, close the app, modify godfingerCfg.json and come back")
            # self._config = config.Config()
            # self._config.cfg = json.loads(CONFIG_FALLBACK)
            # f = open(CONFIG_DEFAULT_PATH, "wt")
            # f.write(CONFIG_FALLBACK)
            # f.close()
            self._status = MBIIServer.STATUS_CONFIG_ERROR;
            return;
    
        if not self.ValidateConfig(self._config):
            self._status = MBIIServer.STATUS_CONFIG_ERROR;
            return;
    
        if "paths" in self._config.cfg:
            for path in self._config.cfg["paths"]:
                sys.path.append(os.path.normpath(path));
        
        Log.debug("System path total %s", str(sys.path));

        self._svInterface = None;
        cfgIface = self._config.GetValue("interface", "pty");
        if cfgIface == "pty":
            self._svInterface = godfingerinterface.PtyInterface(cwd=self._config.cfg["serverPath"],\
                                                                args=[os.path.join(self._config.cfg["serverPath"], self._config.cfg["interfaces"]["pty"]["target"])]\
                                                                + (Args.mbiicmd.split() if Args.mbiicmd else []),\
                                                                inputDelay=self._config.cfg["interfaces"]["pty"]["inputDelay"],\
                                                                );
        elif cfgIface == "rcon":
            self._svInterface = godfingerinterface.RconInterface(   self._config.cfg["interfaces"]["rcon"]["Remote"]["address"]["ip"],\
                                                                    self._config.cfg["interfaces"]["rcon"]["Remote"]["address"]["port"],\
                                                                    self._config.cfg["interfaces"]["rcon"]["Remote"]["bindAddress"],\
                                                                    self._config.cfg["interfaces"]["rcon"]["Remote"]["password"],\
                                                                    os.path.join(self._config.cfg["MBIIPath"], self._config.cfg["interfaces"]["rcon"]["logFilename"]),\
                                                                    self._config.cfg["interfaces"]["rcon"]["logReadDelay"],
                                                                    self._config.cfg["interfaces"]["rcon"]["Debug"]["TestRetrospect"],
                                                                    procName=self._config.cfg["serverFileName"]);
        
        if self._svInterface == None:
            Log.error("Server interface was not initialized properly.");
            self._status = MBIIServer.STATUS_CONFIG_ERROR;
            return;
    
        if IsWindows:
            os.system("title " + self._config.cfg["Name"]);

        # Databases
        self._dbManager = database.DatabaseManager();
        r = self._dbManager.CreateDatabase("Godfinger.db", "Godfinger");
        self._database = self._dbManager.GetDatabase("Godfinger");
        self._database.Open();
        #self._database.LoadExtension("./sqlite_hashes.dll"); no work, python cross platform stuff.

        # Archives
        self._pk3Manager = pk3.Pk3Manager();
        self._pk3Manager.Initialize([self._config.cfg["MBIIPath"]]);

        if not self._svInterface.Open():
            Log.error("Unable to Open server interface.");
            self._status = MBIIServer.STATUS_SERVER_JUST_AN_ERROR;
            return;
        self._svInterface.WaitUntilReady();
        
        # Cvars
        # Init at Start
        self._cvarManager = cvar.CvarManager(self._svInterface);
        
        # Client management
        self._clientManager = clientmanager.ClientManager();

        # Server data handling
        start_sd = time.time();
        exportAPI = godfingerAPI.API();
        exportAPI.GetClientCount    = self.API_GetClientCount;
        exportAPI.GetClientById     = self.API_GetClientById;
        exportAPI.GetClientByName   = self.API_GetClientByName;
        exportAPI.GetAllClients     = self.API_GetAllClients;
        exportAPI.GetCurrentMap     = self.API_GetCurrentMap;
        exportAPI.GetServerVar      = self.API_GetServerVar;
        exportAPI.CreateDatabase    = self.API_CreateDatabase;
        exportAPI.AddDatabase       = self.API_AddDatabase;
        exportAPI.GetDatabase       = self.API_GetDatabase;
        exportAPI.GetPlugin         = self.API_GetPlugin;
        exportAPI.Restart           = self.Restart;
        self._serverData = serverdata.ServerData(self._pk3Manager, self._cvarManager, exportAPI, self._svInterface, Args);
        Log.info("Loaded server data in %s seconds." %(str(time.time() - start_sd)));


        # Technical
        # Plugins
        self._pluginManager = plugin.PluginManager();
        result = self._pluginManager.Initialize(self._config.cfg["Plugins"], self._serverData);
        if not result:
            self._status = MBIIServer.STATUS_PLUGIN_ERROR;
            return;
        self._logicDelayS = self._config.cfg["logicDelay"];
    
        self._isFinished = False;
        self._isRunning = False;
        self._isRestarting = False;
        self._lastRestartTick = 0.0;
        self._restartTimeout = timeout.Timeout();
        self.restartOnCrash = self._config.cfg["restartOnCrash"];
            

        Log.info("The Godfinger initialized in %.2f seconds!\n" %(time.time() - startTime));
    
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
        statusStr = self._svInterface.Status();
        if statusStr != None:
            Log.debug(statusStr);
            splitted = statusStr.splitlines();
            versionSplit = splitted[2].split();
            version = versionSplit[2] + "_" + versionSplit[3];
            gameType = splitted[3].split()[2];
            mapLine = splitted[5];
            splittedMap = mapLine.split();
            mapName = splittedMap[2];
            mode    = int(splittedMap[3][splittedMap[3].find("(")+1:splittedMap[3].rfind(")")]);
            Log.info("Version %s, GameType %s, Mapname %s, Mode %i" %(version, gameType, mapName, mode));
            self._serverData.version = version;
            self._serverData.gameType = gameType;
            self._serverData.mapName = mapName;
            self._serverData.mode = mode;
            l = len( splitted );
            if l > 10:
                for i in range (10, l):
                    line = splitted[i];
                    playerSplit = line.split();
                    if len(playerSplit) >= 6: # hardcode
                        addr = playerSplit[-2];
                        id = int(playerSplit[0]);
                        extraName = len(playerSplit) - 6;
                        name = playerSplit[3];
                        for i in range(extraName):
                            name += " " + playerSplit[4 + i];
                        if name[0] == '(' and name[-1] == ')':
                            name = name[1:-1]   # strip only first and last '(' and ')' chars
                        Log.debug("Status client info addr %s, id %s, name \"%s\"" %(addr, id, name));
                        existing = self._clientManager.GetClientById(id);
                        if existing == None:
                            newClient = client.Client(id, name, addr)
                            self._clientManager.AddClient(newClient);
                        else:
                            if existing.GetName() != name:
                                existing._name = name;
                            if existing.GetAddress() != addr:
                                existing._address = addr;
            playersLine = splitted[6];
            startIndex = playersLine.find("(");
            endIndex = playersLine.find(" max");
            if startIndex != -1 and endIndex != -1:
                self._serverData.maxPlayers = int(playersLine[startIndex+1:endIndex]);
                Log.debug("Status players max count %d"%self._serverData.maxPlayers);
            else:
                self._serverData.maxPlayers = 32;
                Log.warning("Server status is having invalid format, setting default values to status data.");
        else:
            self._serverData.maxPlayers = 32;
            Log.warning("Server status is unreachable, setting default values to status data.");
        pass;

    
    def Restart(self, timeout = 60):
        if not self._isRestarting:
            self._isRestarting = True;
            self._restartTimeout.Set(timeout);
            self._lastRestartTick = timeout;
            self._svInterface.SvSay("^1 {text}.".format(text = "Godfinger Restarting procedure started, ETA %s"%self._restartTimeout.LeftDHMS()));
            Log.info("Restart issued, proceeding.");
    
    def Start(self):
        try:
            # check for server process running first
            sv_fname = self._config.cfg["serverFileName"];
            if not sv_fname in (p.name() for p in psutil.process_iter()):
                self._status = MBIIServer.STATUS_SERVER_NOT_RUNNING;
                if not Args.debug: 
                    Log.error("Server is not running, start the server first, terminating...");
                    return;
                else:
                    Log.debug("Running in debug mode and server is offline, consider server data invalid.");
            
            if not self._cvarManager.Initialize():
                Log.error("Failed to initialize CvarManager, abort startup.");
                self._status = MBIIServer.STATUS_SERVER_JUST_AN_ERROR;
                return;
        
            allCvars = self._cvarManager.GetAllCvars();
            Log.debug("All cvars %s" % str(allCvars));
            
            self._FetchStatus();

            if not self._pluginManager.Start():
                return;
            self._isRunning = True;
            self._status = MBIIServer.STATUS_RUNNING;
            #if Args.debug:
            #    self._svInterface.Test();
            self._svInterface.SvSay("^1 {text}.".format(text = self._config.cfg["prologueMessage"]));
            while self._isRunning:
                startTime = time.time();
                self.Loop();
                elapsed = time.time() - startTime;
                sleepTime = self._logicDelayS - elapsed;
                if sleepTime <= 0:
                    sleepTime = 0;
                time.sleep(sleepTime);  
        except KeyboardInterrupt:
            s = signal.signal(signal.SIGINT, signal.SIG_IGN);
            Log.info("Interrupt recieved.");
            Sighandler(signal.SIGINT, -1);
            
    def Stop(self):
        if self._isRunning:
            Log.info("Stopping Godfinger...");
            self._svInterface.SvSay("^1 {text}.".format(text = self._config.cfg["epilogueMessage"]));
            self._status = MBIIServer.STATUS_STOPPING;
            self._svInterface.Close();
            self._isRunning = False;
            self._status = MBIIServer.STATUS_STOPPED;
            Log.info("Stopped."); 

    def Loop(self):
        if self._isRestarting:
            if self._restartTimeout.IsSet():
                tick = self._restartTimeout.Left();
                if tick - self._lastRestartTick <= -5:
                    self._svInterface.SvSay("^1 {text}.".format(text = "Godfinger is about to restart in %s"%self._restartTimeout.LeftDHMS()));
                    self._lastRestartTick = tick;
            else:
                Sighandler(signal.SIGINT, -1);
                self.restartOnCrash = False;
                self.Stop();
                return;
        messages = self._svInterface.GetMessages();
        while not messages.empty():
            message = messages.get();
            self._ParseMessage(message);
        self._pluginManager.Loop();

    def _ParseMessage(self, message : logMessage.LogMessage):
        
        line = message.content;
        if line.startswith("ShutdownGame"):
            self.OnShutdownGame(message);
            return;
    
        elif line.startswith("gsess"):
            self.OnRealInit(message);
            return;
    
        # maybe its better to move it outside of string parsing
        if line.startswith("wd_"):
            if line == "wd_unavailable":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_UNAVAILABLE,None));
            elif line == "wd_existing":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_EXISTING,None));
            elif line == "wd_started":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_STARTED,None));
            elif line == "wd_died":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_DIED,None));
            elif line == "wd_restarted":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_RESTARTED,None));
            return;

        lineParse = line.split()
        
        # There's a bug with the server logging where a newline is not appended if a 
        # player is dropped due to no launcher, leading to lines getting skipped.
        # We need to check for this message and add the skipped line directly into the
        # Queue's deque object if this is the case            
        badLine = "^3^1Please start the game via ^1launcher and keep it ^1running!"
        idx = line.find(badLine)
        if idx != -1:
            skippedLine = line[idx + len(badLine):]
            # strip timestamp
            skippedLine = skippedLine[7:]
            #if len(skippedLine) > 0:
            #    self._logMessagesQueue.queue.appendleft(logMessage.LogMessage(skippedLine, False));
        l = len(lineParse);
        # we shouldn't ever see blank lines in the server log if it isn't tampered with but just in case
        if l > 1:
            if lineParse[0] == "SMOD":  # Handle SMOD commands
                if lineParse[1] == "say:":      # smod server say (admin message)
                    pass
                elif lineParse[1] == "smsay:":   # smod chat smsay (admin-only chat message)
                    self.OnSmsay(message)
            elif lineParse[1] == "say:":  # Handle say messages by players (not server)
                self.OnChatMessage(message)
            elif lineParse[1] == "sayteam:":
                self.OnChatMessageTeam(message)
            elif lineParse[0] == "Player":
                self.OnPlayer(message); # it's gonna be a long ride
            elif lineParse[0] == "Kill:":
                self.OnKill(message);
            elif lineParse[0] == "Exit:":
                self.OnExit(message);
            if lineParse[0] == "ClientConnect:":
                self.OnClientConnect(message);
            if lineParse[0] == "ClientBegin:":
                self.OnClientBegin(message);
            elif lineParse[0] == "InitGame:":
                self.OnInitGame(message);
            elif lineParse[0] == "ClientDisconnect:":
                self.OnClientDisconnect(message);
            elif lineParse[0] == "ClientUserinfoChanged:":
                self.OnClientUserInfoChanged(message);
            else:
                return;

    # Make it read from bottom to first ServerInit: message, incase if we're started after someone connected, 
    # because rcon status notrunc doesnt provide team info on players
    # def ParseLogThreadHandler(self, control, sleepTime):
    #     with open(self._logPath, "r") as log:
    #         log.seek(0, io.SEEK_END)
    #         while True:
    #             stop = False;
    #             with self._logReaderLock:
    #                 stop = control.stop;
    #             if not stop:
    #                 # Parse server log line
    #                 lines = log.readlines();
    #                 if len(lines) > 0:
    #                     with self._logMessagesLock:
    #                         for line in lines:
    #                             if len(line) > 0:
    #                                 line = line[7:];
    #                                 self._logMessagesQueue.put(logMessage.LogMessage(line));
    #                 else:
    #                     time.sleep(sleepTime)
    #             else:
    #                 break;
    #         log.close();
    
    def OnChatMessage(self, logMessage : logMessage.LogMessage):
        messageRaw = logMessage.content;
        lineParse = messageRaw.split();
        senderId = int(lineParse[0].strip(":"))
        senderClient = self._clientManager.GetClientById(senderId);
        Log.debug("Chat message %s, from client %s" % (messageRaw, str(senderClient)) );
        message : str = messageRaw.split("\"")[1]   # quote characters cannot appear in chat messages, meaning that index 1 will always contain the whole chat message
        self._pluginManager.Event( godfingerEvent.MessageEvent( senderClient, message, { 'messageRaw' : messageRaw }, isStartup = logMessage.isStartup ) );

    def OnChatMessageTeam(self, logMessage : logMessage.LogMessage):
        messageRaw = logMessage.content;
        lineParse = messageRaw.split();
        senderId = int(lineParse[0].strip(":"))
        senderClient = self._clientManager.GetClientById(senderId);
        message : str = messageRaw.split("\"")[1] 
        Log.debug("Team chat meassge %s, from client %s" % (messageRaw, str(senderClient)));
        self._pluginManager.Event( godfingerEvent.MessageEvent( senderClient, message, { 'messageRaw' : messageRaw }, senderClient.GetTeamId(), isStartup = logMessage.isStartup ) );
    
    
    def OnPlayer(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("On Player log entry %s ", textified);
        posUi = textified.find("u");
        if posUi != -1:
            ui = textified[posUi + USERINFO_LEN + 1 : len(textified)-1];
            pi = textified[0:posUi];
            splitted = pi.split();
            pidNum = int(splitted[1]);
            cl = self._clientManager.GetClientById(pidNum);
            if cl != None:
                splitui = ui.split("\\") # should be always last
                vars = {};
                changedOld = {};
                for index in range (0, len(splitui), 2):
                    vars[splitui[index]] = splitui[index+1];
                with cl._lock:
                    newTeamId = teams.TranslateTeam(vars["team"]);
                    if cl.GetTeamId() != newTeamId:
                        # client team changed
                        changedOld["team"] = cl.GetTeamId();
                        cl._teamId = newTeamId;
                    if "name" in vars:
                        if cl.GetName() != vars["name"]:
                            changedOld["name"] = cl.GetName();
                            cl._name = vars["name"];
                    if "ja_guid" in vars:
                        if cl._jaguid != vars["ja_guid"]:
                            changedOld["ja_guid"] = cl._jaguid;
                            cl._jaguid = vars["ja_guid"];
                if len(changedOld) > 0 :
                    self._pluginManager.Event( godfingerEvent.ClientChangedEvent(cl, changedOld, isStartup = logMessage.isStartup ) ); # a spawned client changed
                else:
                    self._pluginManager.Event( godfingerEvent.PlayerSpawnEvent ( cl, vars,  isStartup = logMessage.isStartup ) ); # a newly spawned client
            else:
                Log.warning("Client \"Player\" event with client is None.");
        self._pluginManager.Event( godfingerEvent.PlayerEvent(cl, {"text":textified}, isStartup = logMessage.isStartup));   


    def OnKill(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("Kill log entry %s", textified);
        splitted = textified.split();
        pidNum = splitted[1];
        victimNum = splitted[2];
        cl = self._clientManager.GetClientById(int(pidNum));
        clVictim = self._clientManager.GetClientById(int(victimNum));
        if cl != None and clVictim != None:
            weaponStr = splitted[-1];
            if cl is clVictim:
                if weaponStr == "MOD_WENTSPECTATOR":
                    # dude changed their team to spectator with self kill
                    oldTeam = cl.GetTeamId();
                    cl._teamId = teams.TEAM_SPEC;
                    self._pluginManager.Event( godfingerEvent.ClientChangedEvent(cl, {"team":oldTeam} , isStartup = logMessage.isStartup))
            self._pluginManager.Event( godfingerEvent.KillEvent(cl, clVictim, weaponStr, None, isStartup = logMessage.isStartup ) );
    
    def OnExit(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        textsplit = textified.split()
        Log.debug("Exit log entry %s", textified);
        scoreLine = None
        playerScores = {}
        for m in self._svInterface.GetMessages().queue:
            if m.startswith("red:"):
                scoreLine = m
            elif m.startswith("score:"):
                scoreParse = m.split()
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
        self._pluginManager.Event( godfingerEvent.ExitEvent( {"reason" : exitReason, "teamScores" : teamScores, "playerScores" : playerScores}, isStartup = logMessage.isStartup ) );


    def OnClientConnect(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("Client connect log entry %s", textified);
        lineParse = textified.split();
        extraName = len(lineParse) - 6;
        id = int(lineParse[3 + extraName]);
        ip = lineParse[-1].strip(")");
        name = lineParse[1];
        for i in range(extraName):
            name += " " + lineParse[2 + i];
        if name[0] == '(' and name[-1] == ')':
            name = name[1:-1]   # strip only first and last '(' and ')' chars
        Log.debug("Client info parsed: ID: %s; IP: %s; Name: %s", str(id), ip, name );
        if not id in [cl.GetId() for cl in self.API_GetAllClients()]:
            newClient = client.Client(id, name, ip);
            self._clientManager.AddClient(newClient); # make sure its added BEFORE events are processed
            self._pluginManager.Event( godfingerEvent.ClientConnectEvent( newClient, None, isStartup = logMessage.isStartup ) );
        else:
            Log.warning(f"Duplicate client with ID {id} connected, ignoring")
            pass

    def OnClientBegin(self, logMessage : logMessage.LogMessage ):
        textified = logMessage.content;
        #Log.debug("Client begin log entry %s", textified);
        lineParse = textified.split();
        clientId = int(lineParse[1]);
        client = self._clientManager.GetClientById(clientId);
        if client != None:
            pass;
            #Log.debug("Client is not none, sending begin event to plugins.");
            self._pluginManager.Event( godfingerEvent.ClientBeginEvent( client, {}, isStartup = logMessage.isStartup ) );
    
    def OnClientDisconnect(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("Client disconnect log entry %s", textified); 
        lineParse = textified.split();
        dcId = int(lineParse[1]);
        cl = self._clientManager.GetClientById(dcId);
        if cl != None:
            Log.debug("Player with dcId %s disconnected ", str(dcId));
            self._pluginManager.Event( godfingerEvent.ClientDisconnectEvent( cl, None, isStartup = logMessage.isStartup ) );
            self._clientManager.RemoveClient(cl); # make sure its removed AFTER events are processed by plugins
            if self._clientManager.GetClientCount() == 0:
                Log.debug("All players have left the server");
                self._pluginManager.Event( godfingerEvent.ServerEmptyEvent(isStartup = logMessage.isStartup));
        else:
            pass # player reconnected ( thats how server shits in logs for some reason)

    def OnClientUserInfoChanged(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("Client user info changed log entry %s", textified);
        lineParse = textified.split();
        clientId = int(lineParse[1])
        userInfo = textified[23 + len(lineParse[1]):].strip()  # easier if we just ignore everything up until the variables
        cl = self._clientManager.GetClientById(clientId);
        if cl != None:
            cl.Update(userInfo);
            self._pluginManager.Event( godfingerEvent.ClientChangedEvent( cl, cl.GetInfo(), isStartup = logMessage.isStartup ) );
        else:
            Log.warning(f"Attempted to update userinfo of client {clientId} which does not exist, ignoring")

    def OnInitGame(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("Init game log entry %s", textified);
        configStr = textified[len("InitGame: \\"):len(textified)];
        vars = {};
        splitted = configStr.split("\\");
        for index in range (0, len(splitted), 2):
            vars[splitted[index]] = splitted[index+1];
            
        if "mapname" in vars:
            if vars["mapname"] != self._serverData.mapName:
                print("mapname cvar parsed, applying " + vars["mapname"] + " : " + self._serverData.mapName);
                if self._serverData.mapName != '':          # ignore first map ;
                    self.OnMapChange(vars["mapname"], self._serverData.mapName)
                self._serverData.mapName = vars["mapname"];
        else:
            self._serverData.mapName = self._svInterface.GetCurrentMap();
        
        Log.info("Current map name on init : %s", self._serverData.mapName);
        
        self._pluginManager.Event( godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_INIT, { "vars" : vars }, isStartup = logMessage.isStartup ) );
        self._pluginManager.Event( godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT, {}, isStartup = logMessage.isStartup ) );

    def OnShutdownGame(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug("Shutdown game log entry %s", textified);
        allClients = self._clientManager.GetAllClients();
        #with self._clientManager._lock:
        for client in allClients:
            Log.debug("Shutdown pseudo-disconnecting client %s" %str(client));
           # self._pluginManager.Event( godfingerEvent.ClientDisconnectEvent( client, {}, godfingerEvent.ClientDisconnectEvent.REASON_SERVER_SHUTDOWN, isStartup = logMessage.isStartup ) );
        
        self._pluginManager.Event( godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN, None, isStartup = logMessage.isStartup ) );
    
    def OnRealInit(self, logMessage : logMessage.LogMessage):
        Log.debug("Server starting up for real.");
        self._pluginManager.Event(godfingerEvent.Event( godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT, None, isStartup = logMessage.isStartup ));

    def OnMapChange(self, mapName : str, oldMapName : str):
        Log.debug(f"Map change event received: {mapName}")
        self._pluginManager.Event(godfingerEvent.MapChangeEvent(mapName, oldMapName));

    def OnSmsay(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content;
        Log.debug(f"Smod say event received: {textified}")
        lineSplit = textified.split()
        adminIDIndex = lineSplit.index('(adminID:')
        if adminIDIndex != -1:
            smodID = lineSplit[adminIDIndex + 1].strip(")")
            senderName = ' '.join(lineSplit[2:adminIDIndex])
            senderIP = lineSplit[adminIDIndex + 3].strip("):")
            message = ' '.join(lineSplit[adminIDIndex + 4:])
            self._pluginManager.Event(godfingerEvent.SmodSayEvent(senderName, int(smodID), senderIP, message, isStartup = logMessage.isStartup))
        else:
            # somehow malformed smsay message 
            pass

    # API export functions 
    def API_GetClientById(self, id):
        return self._clientManager.GetClientById(id);

    def API_GetClientByName(self, name):
        return self._clientManager.GetClientByName(name);

    def API_GetAllClients(self):
        return self._clientManager.GetAllClients();

    def API_GetClientCount(self):
        return self._clientManager.GetClientCount();

    def API_GetCurrentMap(self):
        return "" + self._serverData.mapName;

    def API_GetServerVar(self, var):
        return self._serverData.GetServerVar(var)

    def API_SetServerVar(self, var, val):
        self._serverData.SetServerVar(var, val)

    def API_CreateDatabase(self, path, name) -> int:
        return self._dbManager.CreateDatabase(path, name);

    def API_AddDatabase(self, db : database.ADatabase) -> int:
        return self._dbManager.AddDatabase(db);
    
    def API_GetDatabase(self, name) -> database.ADatabase:
        return self._dbManager.GetDatabase(name);

    def API_GetPlugin(self, name) -> plugin.Plugin:
        return self._pluginManager.GetPlugin(name);

    def API_Restart(self, timeout = 60):
        self.Restart(timeout);

    def IsRestarting(self) -> bool:
        return self._isRestarting;

def InitLogger():
    loggingMode = logging.INFO;
    loggingFile = "";

    if Args.debug:
        print("DEBUGGING MODE.");
        loggingMode = logging.DEBUG;
    if Args.logfile:
        print("Logging into file");
        loggingFile = Args.logfile;
    
    if loggingFile != "":
        logging.basicConfig(
        filename = loggingFile,
        level = loggingMode,
        filemode = 'w+',
        #level=logging.INFO,
        format='%(asctime)s %(levelname)08s %(name)s %(message)s',
        )
    else:
        logging.basicConfig(
        level = loggingMode,
        filemode = 'w+',
        #level=logging.INFO,
        format='%(asctime)s %(levelname)08s %(name)s %(message)s',
        )

def main():
    InitLogger();
    Log.info("Godfinger entry point.");
    global Server;
    Server = MBIIServer();
    int_status = Server.GetStatus();
    runAgain = True;
    if int_status == MBIIServer.STATUS_INIT:
        while runAgain:
            try:
                runAgain = False;
                Server.Start();  # it will exit the Start on user shutdown
            except Exception as e:
                Log.error(f"ERROR occurred: Type: {type(e)}; Reason: {e}; Traceback: {traceback.format_exc()}")
                try:
                    with open('lib/other/gf.txt', 'r') as file:
                        gf = file.read()
                        print("\n\n" + gf)
                        file.close()
                except Exception as e:
                    Log.error(f"ERROR occurred: No fucking god finger.txt");
                print("\n\nCRASH DETECTED, CHECK LOGS");
                Server.Finish()
                if Server.restartOnCrash:
                    runAgain = True;
                    Server = MBIIServer();
                    if int_status == MBIIServer.STATUS_INIT:
                        continue  # start new server instance
                    else:
                        break
        int_status = Server.GetStatus();
        if int_status == MBIIServer.STATUS_SERVER_NOT_RUNNING:
            print("Unable to start with not running server for safety measures, abort init.");
        Server.Finish();
        if Server.IsRestarting():
            del Server
            Server = None;
            cmd = (" ".join( sys.argv ) );
            dir = os.path.dirname(__file__);
            cmd = os.path.normpath(os.path.join(dir, cmd));
            cmd = (sys.executable + " " + cmd );
            subprocess.Popen(cmd, creationflags=subprocess.DETACHED_PROCESS);
            sys.exit();
        del Server
        Server = None;
    else:
        Log.info("Godfinger initialize error %s" % (MBIIServer.StatusString(int_status)));
    
    Log.info("The final gunshot was an exclamation mark on everything that had led to this point. I released my finger from the trigger, and it was over.");


if __name__ == "__main__":
    main();
