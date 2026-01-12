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
import queue

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
# queue imported at top
import database
import plugin
import lib.shared.teams as teams
import logMessage
import math
import lib.shared.colors as colors
import cvar
import godfingerinterface
import lib.shared.timeout as timeout
import lib.shared.pswd as pswd
import lib.shared.observer as observer

INVALID_ID = -1
USERINFO_LEN = len("userinfo: ")

CONFIG_DEFAULT_PATH = os.path.join(os.getcwd(),"godfingerCfg.json")
# Things like port and ip can be omitted in future, since this thing is supposed to be sharing the filesystem with the server, it could read it's config for credentials.
CONFIG_FALLBACK = \
"""{
    "Name":"MBII Godfinger : Consequetive Failure",
    "MBIIPath": "your/path/here/",
    "logFilename":"server.log",
    "serverPath":"your/path/here/",
    "serverFileName":"mbiided.x86.exe",
    "logicDelay":0.016,
    "restartOnCrash": false,
    "watchdog": {
        "enabled": false,
        "restartServer": false,
        "serverStartCommand": ""
    },
    "floodProtection": {
        "enabled": false,
        "soft": false,
        "seconds": 1.5
    },

    "interfaces":
    {
        "pty":
        {
            "target":"path/to/your/mbiided.exe",
            "inputDelay":0.001
        },
        "rcon":
        {
            "ip":"localhost",
            "bindAddress":"localhost",
            "logReadDelay":0.1,

            "Remotes": [
                {
                    "port":29070,
                    "logFilename":"server.log",
                    "password":"fuckmylife"
                }
            ],

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
        # Server/Game path and name are global properties, check them
        if cfg.GetValue("MBIIPath", None) in [None, "your/path/here/"]:
            return False
        if cfg.GetValue("serverFileName", None) in [None, ""]:
            return False
        if cfg.GetValue("serverPath", None) in [None, "your/path/here/"]:
            return False

        curVar = cfg.GetValue("interface", None)
        if curVar == None or ( curVar != "pty" and curVar != "rcon" ):
            return False
        elif curVar == "pty":
            Log.error("pty Interface is not fully implemented, use rcon instead.")
            return False
        elif curVar == "rcon":
            rcon_cfg = cfg.cfg["interfaces"]["rcon"]
            # REFACTORED: "Debug" is now included in the list of top-level required keys again
            required_rcon_keys = ["ip", "bindAddress", "logReadDelay", "Remotes", "Debug"]
            for key in required_rcon_keys:
                if key not in rcon_cfg:
                    Log.error(f"Rcon interface config is missing the required key '{key}'.")
                    return False

            # NEW: Validate the structure of the top-level Debug block
            if not isinstance(rcon_cfg["Debug"], dict) or "TestRetrospect" not in rcon_cfg["Debug"]:
                 Log.error("Rcon interface config 'Debug' is missing the required 'TestRetrospect' setting.")
                 return False

            if not isinstance(rcon_cfg["Remotes"], list) or len(rcon_cfg["Remotes"]) == 0:
                Log.error("Rcon interface config 'Remotes' is not a list or is empty.")
                return False

            # NEW: Validate that each remote has a password (Debug check is removed from here)
            for idx, remote_cfg in enumerate(rcon_cfg["Remotes"]):
                if "password" not in remote_cfg:
                    Log.error(f"Rcon remote #{idx+1} is missing a required 'password' setting.")
                    return False
        return True


    def GetStatus(self):
        return self._status

    def __init__(self):
        self._isFinished = False
        self._isRunning = False
        self._isRestarting = False
        self._pluginManager = None
        self._svInterfaces = [] # NEW: List of interfaces
        self._primarySvInterface = None # NEW: Primary interface for status/commands
        self._gatheringExitData = False
        self._exitLogMessages = []

        startTime = time.time()
        self._status = MBIIServer.STATUS_INIT
        Log.info("Initializing Godfinger...")
        # Config load first
        self._config = config.Config.from_file(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)
        if self._config == None:
            Log.error("Failed to load Godfinger config.")
            self._status = MBIIServer.STATUS_CONFIG_ERROR
            return

        if not self.ValidateConfig(self._config):
            Log.error("Godfinger config validation failed.")
            self._status = MBIIServer.STATUS_CONFIG_ERROR
            return

        # Set default watchdog command based on platform if not specified
        if "watchdog" in self._config.cfg:
            if not self._config.cfg["watchdog"].get("serverStartCommand", ""):
                if IsWindows:
                    # Use autostart script which only starts MB2 server, not Godfinger
                    self._config.cfg["watchdog"]["serverStartCommand"] = os.path.join(os.getcwd(), "start", "win", "bin", "autostart_win.py")
                else:
                    # Use autostart script which only starts MB2 server, not Godfinger
                    self._config.cfg["watchdog"]["serverStartCommand"] = os.path.join(os.getcwd(), "start", "unix", "bin", "autostart_unix.py")
                Log.debug(f"Set default watchdog command: {self._config.cfg['watchdog']['serverStartCommand']}")

        if "paths" in self._config.cfg:
            for path in self._config.cfg["paths"]:
                sys.path.append(os.path.normpath(path))

        Log.debug("System path total %s", str(sys.path))

        cfgIface = self._config.GetValue("interface", "pty")

        if cfgIface == "pty":
            # NOTE: PtyInterface is only supported as a single interface connection
            self._svInterfaces.append(godfingerinterface.PtyInterface(cwd=self._config.cfg["serverPath"],\
                                                                args=[os.path.join(self._config.cfg["serverPath"], self._config.cfg["interfaces"]["pty"]["target"])]\
                                                                + (Args.mbiicmd.split() if Args.mbiicmd else []),\
                                                                inputDelay=self._config.cfg["interfaces"]["pty"]["inputDelay"],\
                                                                ))
        elif cfgIface == "rcon":
            rcon_cfg = self._config.cfg["interfaces"]["rcon"]
            global_logFilename = self._config.cfg["logFilename"]

            # REFACTORED: Read shared/top-level properties
            shared_ip = rcon_cfg["ip"]
            shared_bindAddress = rcon_cfg["bindAddress"]
            shared_logReadDelay = rcon_cfg["logReadDelay"]
            shared_testRetrospect = rcon_cfg["Debug"]["TestRetrospect"] # Re-read from top level Debug block

            # NEW: Loop over Remotes list, getting password and connection details from each remote
            for idx, remote_cfg in enumerate(rcon_cfg["Remotes"]):
                remote_ip = remote_cfg.get("ip", shared_ip)
                remote_logFilename = remote_cfg.get("logFilename", global_logFilename)
                remote_port = remote_cfg.get("port", 0) # Port is mandatory for Rcon, but use 0 as a safe sentinel

                # NEW: Get password from remote config
                remote_password = remote_cfg["password"]

                if remote_port == 0:
                    Log.error(f"Rcon remote #{idx+1} is missing a required 'port' setting. Skipping.")
                    continue

                interface = godfingerinterface.RconInterface(
                                                                    remote_ip,\
                                                                    remote_port,\
                                                                    shared_bindAddress,\
                                                                    remote_password,\
                                                                    os.path.join(self._config.cfg["MBIIPath"], remote_logFilename),\
                                                                    shared_logReadDelay,
                                                                    shared_testRetrospect, # Uses shared/top-level value
                                                                    procName=self._config.cfg["serverFileName"])
                self._svInterfaces.append(interface)
                Log.info(f"Initialized RconInterface #{idx+1} on {remote_ip}:{remote_port} (Bind: {shared_bindAddress}) using log file {remote_logFilename}")

        if len(self._svInterfaces) == 0:
            Log.error("Server interface(s) were not initialized properly or 'Remotes' list was empty.")
            self._status = MBIIServer.STATUS_CONFIG_ERROR
            return

        self._primarySvInterface = self._svInterfaces[0] # Use the first interface for sending commands and status checks

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

        # NEW: Open all interfaces
        for interface in self._svInterfaces:
            if not interface.Open():
                Log.error(f"Unable to Open server interface: {interface}")
                self._status = MBIIServer.STATUS_SERVER_JUST_AN_ERROR
                return
            interface.WaitUntilReady()

        # Cvars
        self._cvarManager = cvar.CvarManager(self._primarySvInterface) # Use primary interface for Cvars

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
        self._serverData = serverdata.ServerData(self._pk3Manager, self._cvarManager, exportAPI, self._primarySvInterface, Args) # Use primary interface
        extralives_path = os.path.join(os.path.dirname(__file__), "data", "extralives.json")
        try:
            with open(extralives_path, "r") as f:
                extralives_data = json.load(f)
                if extralives_data and "characters" in extralives_data:
                    self._serverData.extralives_map = {
                        char: details["extralives"]
                        for char, details in extralives_data["characters"].items()
                        if "extralives" in details
                    }
                else:
                    self._serverData.extralives_map = {}
        except FileNotFoundError:
            Log.error(f"extralives.json not found at {extralives_path}")
        except json.JSONDecodeError:
            Log.error(f"Error decoding extralives.json at {extralives_path}")
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

        # Log watchdog configuration
        if self._config.cfg.get("watchdog", {}).get("enabled", False):
            Log.info(f"Watchdog restart enabled for MB2 server process '{self._config.cfg['serverFileName']}'")

        Log.info("The Godfinger initialized in %.2f seconds!\n" %(time.time() - startTime))

    def _HandleWatchdogEvent(self, event_type):
        """Handle watchdog events from the RconInterface watchdog"""
        try:
            watchdog_config = self._config.cfg.get("watchdog", {})

            # Only process events if watchdog is enabled
            if not watchdog_config.get("enabled", False):
                return

            server_name = self._config.cfg["serverFileName"]

            if event_type == "unavailable":
                Log.warning(f"Watchdog: MB2 server process '{server_name}' is not running")
            elif event_type == "existing":
                Log.info(f"Watchdog: MB2 server process '{server_name}' is running")
            elif event_type == "died":
                Log.error(f"Watchdog: MB2 server process '{server_name}' has died!")

                # Attempt to restart server if configured
                if watchdog_config.get("restartServer", False):
                    restart_cmd_path = watchdog_config.get("serverStartCommand", "")

                    if not restart_cmd_path:
                        Log.error(f"Watchdog: serverStartCommand is not configured")
                        return

                    # Check if script exists
                    if not os.path.exists(restart_cmd_path):
                        Log.error(f"Watchdog: Start script not found at {restart_cmd_path}")
                        return

                    Log.info(f"Watchdog: Attempting to restart MB2 server with: {restart_cmd_path}")
                    try:
                        # Use current working directory for scripts
                        working_dir = os.getcwd()

                        # Determine if this is a Python script or executable
                        is_python_script = restart_cmd_path.endswith('.py')

                        if is_python_script:
                            # Execute Python script with the same Python interpreter
                            if IsWindows:
                                # Windows: Run python script in detached process
                                subprocess.Popen([sys.executable, restart_cmd_path], cwd=working_dir, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                            else:
                                # Unix: Run python script in background
                                subprocess.Popen([sys.executable, restart_cmd_path], cwd=working_dir, stdin=None, stdout=None, stderr=None, close_fds=True, start_new_session=True)
                        else:
                            # Execute batch/shell script
                            if IsWindows:
                                restart_cmd = f'start "" "{restart_cmd_path}"'
                                subprocess.Popen(restart_cmd, shell=True, cwd=working_dir, creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
                            else:
                                restart_cmd = f'nohup "{restart_cmd_path}" > /dev/null 2>&1 &'
                                subprocess.Popen(restart_cmd, shell=True, cwd=working_dir, stdin=None, stdout=None, stderr=None, close_fds=True, start_new_session=True)

                        Log.info("Watchdog: MB2 server restart command executed successfully")
                    except Exception as e:
                        Log.error(f"Watchdog: Failed to restart MB2 server: {e}")
            elif event_type == "started":
                Log.info(f"Watchdog: MB2 server process '{server_name}' has started")
            elif event_type == "restarted":
                Log.info(f"Watchdog: MB2 server process '{server_name}' has been restarted")
        except Exception as e:
            Log.error(f"Error in watchdog event handler: {e}")

    def Finish(self,):
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
        # NEW: Delete all interfaces
        if hasattr(self, "_svInterfaces"):
            for interface in self._svInterfaces:
                del interface
            self._svInterfaces = []
            self._primarySvInterface = None


    # status notrunc
    def _FetchStatus(self):
        # NEW: Use primary interface for status
        statusStr = self._primarySvInterface.Status()
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
            self._lastRestartTick = 0.0
            # Use primary interface to send command
            self._primarySvInterface.SvSay("^1 {text}.".format(text = "Godfinger Restarting procedure started, ETA %s"%self._restartTimeout.LeftDHMS()))
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

            # Use primary interface for CvarManager
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
            # Use primary interface for SvSay
            self._primarySvInterface.SvSay("^1 {text}.".format(text = self._config.cfg["prologueMessage"]))
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
            # Use primary interface for SvSay
            if self._primarySvInterface:
                self._primarySvInterface.SvSay("^1 {text}.".format(text = self._config.cfg["epilogueMessage"]))
            self._status = MBIIServer.STATUS_STOPPING
            # NEW: Close all interfaces
            for interface in self._svInterfaces:
                interface.Close()
            self._isRunning = False
            self._status = MBIIServer.STATUS_STOPPED
            Log.info("Stopped.")

    def Loop(self):
        if self._isRestarting:
            if self._restartTimeout.IsSet():
                tick = self._restartTimeout.Left()
                if tick - self._lastRestartTick <= -5:
                    # Use primary interface for SvSay
                    self._primarySvInterface.SvSay("^1 {text}.".format(text = "Godfinger is about to restart in %s"%self._restartTimeout.LeftDHMS()))
                    self._lastRestartTick = tick
            else:
                Sighandler(signal.SIGINT, -1)
                self.restartOnCrash = False
                self.Stop()
                return

        # NEW: Process messages from all interfaces
        for interface in self._svInterfaces:
            messages = interface.GetMessages()
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
                self._HandleWatchdogEvent("unavailable")
            elif line == "wd_existing":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_EXISTING,None))
                self._HandleWatchdogEvent("existing")
            elif line == "wd_started":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_STARTED,None))
                self._HandleWatchdogEvent("started")
            elif line == "wd_died":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_DIED,None))
                self._HandleWatchdogEvent("died")
            elif line == "wd_restarted":
                self._pluginManager.Event(godfingerEvent.Event(godfingerEvent.GODFINGER_EVENT_TYPE_WD_RESTARTED,None))
                self._HandleWatchdogEvent("restarted")
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
            elif line.endswith(") completed the objective!"):
                self.OnObjective(message)
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
                
                # Flood Protection
                floodProtectionConfig = self._config.GetValue("floodProtection", {
                    "enabled": False,
                    "soft": False,
                    "seconds": 1.5
                })

                if floodProtectionConfig["enabled"] and senderClient and len(cmdArgs) > 0:
                    command = cmdArgs[0].lower()
                    if senderClient._floodProtectionCooldown.IsSet():
                        if (floodProtectionConfig["soft"] and command == senderClient._lastCommand) or not floodProtectionConfig["soft"]:
                            return
                    senderClient._floodProtectionCooldown.Set(floodProtectionConfig["seconds"])
                    senderClient._lastCommand = command

                if len(cmdArgs) > 0 and cmdArgs[0] == "help":
                    # Handle help command directly
                    self.HandleChatHelp(senderClient, teams.TEAM_GLOBAL, cmdArgs)
                    return  # Don't pass to plugins
            self._pluginManager.Event( godfingerEvent.MessageEvent( senderClient, message, { 'messageRaw' : messageRaw }, isStartup = logMessage.isStartup ) )
        else:
            pass

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

    def OnPlayer(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("On Player log entry %s", textified)

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

                # Set the upper bound of the loop to be len(splitui) - 1
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
                    self._primarySvInterface.Say('^1[Godfinger]: ^7' + helpText)
                    return True
            # Command not found
            self._primarySvInterface.Say(f"^1[Godfinger]:^7 Couldn't find chat command: {commandName}")
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
                self._primarySvInterface.BatchExecute("b", [f"say {'^1[Godfinger]: ^7' + msg}" for msg in messages])
            else:
                self._primarySvInterface.Say('^1[Godfinger]: ^7' + commandStr)

        return True

    def OnObjective(self, logMessage : logMessage.LogMessage):
        messageRaw = logMessage.content
        # using regex to extract player ID
        match = re.search(r'\(ID: (\d+)\)', messageRaw)
        if match:
            player_id = int(match.group(1))
            cl = self._clientManager.GetClientById(player_id)
            if cl:
                self._pluginManager.Event(godfingerEvent.ObjectiveEvent(cl, {"messageRaw": messageRaw}, isStartup=logMessage.isStartup))
        else:
            Log.error("Unable to retrieve player ID from objective message")
            return False
            
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
                    self._primarySvInterface.SmSay(helpText)
                    return True
            # Command not found
            self._primarySvInterface.SmSay(f"Couldn't find smod command: {commandName}")
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
                self._primarySvInterface.BatchExecute("b", [f"smsay {'^1[Godfinger]: ^7' + msg}" for msg in messages])
            else:
                self._primarySvInterface.SmSay('^1[Godfinger]: ^7' + commandStr)
        return True

    def OnKill(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Kill log entry %s", textified)

        # Split the log message into parts using ': ' as the delimiter, limiting to 2 splits.
        parts = textified.split(": ", 2)

        kill_part = ""
        numeric_part = ""
        message_part = ""

        # --- Safe Unpacking Logic ---
        if len(parts) >= 3:
            kill_part = parts[0]
            numeric_part = parts[1]
            message_part = ": ".join(parts[2:])

        elif len(parts) == 2:
            kill_part = parts[0]
            numeric_part = ""
            message_part = parts[1]

        else:
            return

        if not numeric_part:
            Log.error(f"Kill message missing Player IDs. Log: {textified}")
            return

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
            # 1. Strip color codes
            stripped_token = colors.StripColorCodes(token_to_check)

            # 2. Strip surrounding punctuation (like '(', ')') and whitespace.
            cleaned_token = stripped_token.strip("()").strip()

            # 3. Safely convert the cleaned token to an integer.
            id = int(cleaned_token)

        except ValueError:
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
            pass

    def OnClientUserInfoChanged(self, logMessage : logMessage.LogMessage):
        textified = logMessage.content
        Log.debug("Client user info changed log entry %s", textified)
        lineParse = textified.split()
        clientId = int(lineParse[1])
        userInfoString = textified[23 + len(lineParse[1]):].strip()

        cl = self._clientManager.GetClientById(clientId)
        if cl is None:
            Log.warning(f"Attempted to update userinfo of client {clientId} which does not exist, ignoring")
            return

        if not userInfoString or userInfoString == "0":
            Log.warning(f"Received invalid or empty userinfo '{userInfoString}' for client {clientId}, ignoring update.")
            return

        # Parse userinfo string into a dictionary
        userInfoDict = {}
        parts = userInfoString.split("\\")
        # Handle potential empty strings from splitting
        if len(parts) > 1:
            for i in range(0, len(parts) - 1, 2):
                if parts[i] and parts[i+1]: # Ensure key and value are not empty
                    userInfoDict[parts[i]] = parts[i+1]

        if len(userInfoDict) == 0:
            Log.warning(f"Could not parse userinfo string '{userInfoString}' for client {clientId}, ignoring update.")
            return

        cl.Update(userInfoDict)
        self._pluginManager.Event(godfingerEvent.ClientChangedEvent(cl, cl.GetInfo(), isStartup=logMessage.isStartup))

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
                Log.debug("mapname cvar parsed, applying " + vars["mapname"] + " : OLD " + self._serverData.mapName)
                if self._serverData.mapName != '':          # ignore first map ;
                    self.OnMapChange(vars["mapname"], self._serverData.mapName)
                self._serverData.mapName = vars["mapname"]
        else:
            self._serverData.mapName = self._primarySvInterface.GetCurrentMap()

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
                    del Server
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
