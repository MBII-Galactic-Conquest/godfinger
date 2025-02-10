import threading
import lib.campaignrotation as campaignrotation;
import lib.teamconfig as teamconfig;
import lib.pk3 as pk3;
import godfingerAPI;
import datetime;
import lib.rcon as rcon;



class ServerData():
    def __init__(self, pk3mngr : pk3.Pk3Manager, API : godfingerAPI.API, rcon : rcon.Rcon, args):
        self.pk3Manager = pk3mngr;
        self.API = API;
        self.args = args;
        self.lock = threading.Lock()
        self.serverVars = {}
        self.mapName = "";
        self.rcon = rcon;
        self.maxPlayers = 0;
        self.realInit = False;

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