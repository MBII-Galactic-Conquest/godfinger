import threading
import lib.shared.pk3 as pk3;
import godfingerAPI;
import lib.shared.rcon as rcon;
import cvar;
import godfingerinterface;

class ServerData():

    def __init__(self, pk3mngr : pk3.Pk3Manager, cvarManager : cvar.CvarManager, API : godfingerAPI.API, iface : godfingerinterface.IServerInterface, args):
        self.pk3Manager = pk3mngr;
        self.cvarManager = cvarManager;
        self.API = API;
        self.args = args;
        self.lock = threading.Lock()
        self.serverVars = {}
        # self.rcon = rcon;
        self.interface = iface;
        self.maxPlayers = 0;
        self.version = "";
        self.gameType = "";
        self.mapName = "";
        self.mode = -1;
        self.extralives_map = {}
    
    def GetInterfaceType(self):
        return self.interface.GetType();

    def GetServerVar(self, var) -> object:
        with self.lock:
            if var in self.serverVars:
                return self.serverVars[var]
            else:
                return None
    
    def SetServerVar(self, var, val) -> None:
        with self.lock:
            self.serverVars[var] = val
    
    def UnsetServerVar(self, var) -> bool:
        with self.lock:
            if var in self.serverVars:
                del self.serverVars[var]
                return True
            else:
                return False

    def __repr__(self):
        return "Server data\n";