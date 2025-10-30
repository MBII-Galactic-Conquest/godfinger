import logging
import lib.shared.teams as teams;
import threading;

log = logging.getLogger(__name__)

class Client(object):
    def __init__(self, id : int, name : str, address : str):
        self._lock = threading.Lock();
        self._id = id;
        self._name = name;
        self._address = address;
        self._ip = address[:address.rfind(":")];
        self._teamId = teams.TEAM_SPEC;
        self._jaguid = "";
        self._userinfo = {};
        self._lastNonSpecTeamId = None;
    
    def GetId(self) -> int:
        return self._id;

    def GetName(self) -> str:
        return self._name;

    def GetAddress(self) -> str:
        return self._address
    
    def GetIp(self) -> str:
        return self._ip;
    
    def GetTeamId(self) -> int:
        return self._teamId;

    def GetInfo(self) -> dict[str, str]:
        return self._userinfo;

    def GetLastNonSpecTeamId(self) -> int:
        return self._lastNonSpecTeamId;

    def __repr__(self):
        s = f"{self._name} (ID : {str(self._id)}) (Name : {self._name}) (TeamId : {self._teamId})";
        return s
    

    """
    Userinfo key translation:
    n - player name
    t -  current player team
    m - player model
    c1 - saber color 1
    c2 - saber color 2
    sc - formerly "siegeclass" class name for FA
    s1 - saber 1 hilt
    s2 - saber 2 hilt
    sdt -  desired team (should be same as "t" unless the player is trying to swap teams)
    v -  FA model variant
    s - FA saber hilt variant
    mbc - current class
    """
    
    def Update(self, data : str):
        data = data.split("\\")
        for i in range(0, len(data), 2):
            key = data[i]
            value = data[i+1]
            if key == "n" and self._name != value:
                # logMessage(f"Client {self} has changed their name to {value}")
                self._name = value
            if key == "t" and (teams.TranslateTeam(int(self._teamId)) != teams.TranslateTeam(int(value)) or self._teamId == None):
                # if teams.TranslateTeam(int(value)) != "s":     # ignore spectator since the game switches your team to spectator at the beginning of each round, messing with voting.
                self._teamId = int(value)
                log.info(f"Client {self} has joined team {self._teamId}")
                if self._teamId != teams.TEAM_SPEC:
                    self._lastNonSpecTeamId = self._teamId
            self._userinfo[key] = value
