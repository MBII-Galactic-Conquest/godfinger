from enum import Enum, auto
import json
import logging
import os
from math import ceil, floor
from random import sample
from time import sleep, time
from zipfile import ZipFile

import godfingerEvent
import lib.shared.client as client
import lib.shared.config as config
import lib.shared.player as player
import lib.shared.serverdata as serverdata
import lib.shared.teams as teams
import lib.shared.colors as colors
from lib.shared.player import Player
from lib.shared.timeout import Timeout

SERVER_DATA = None

DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "rtvConfig.json");
DEFAULT_CFG = config.Config.fromJSON(DEFAULT_CFG_PATH)

CONFIG_FALLBACK = \
"""{
    "MBIIPath": "your/mbii/path/here",
    "pluginThemeColor" : "green",
    "MessagePrefix": "[RTV]^7: ",
    "RTVPrefix": "!",
    "requirePrefix" : false,
    "kickProtectedNames" : true,
    "useSayOnly" : false,
    "floodProtection" :
    {
        "enabled" : false,
        "seconds" : 0
    },
    "rtv" : 
    {
        "enabled" : true,
        "voteTime" : 180,
        "voteAnnounceTimer" : 30,
        "voteRequiredRatio" : 0.5,
        "automaticMaps" : true,
        "primaryMaps" : 
        [
            
        ],
        "secondaryMaps" : 
        [
            
        ],
        "useSecondaryMaps" : 1,
        "mapBanList" : 
        [
            "yavin1",
            "yavin1b",
            "yavin2",
            "vjun1",
            "vjun2",
            "vjun3",
            "taspir1",
            "taspir2",
            "t1_danger",
            "t1_fatal",
            "t1_inter",
            "t1_rail",
            "t1_sour",
            "t1_surprise",
            "t2_wedge",
            "t2_trip",
            "t2_rogue",
            "t2_rancor",
            "t2_dpred",
            "t3_bounty",
            "t3_byss",
            "t3_hevil",
            "t3_rift",
            "t3_stamp",
            "kor1",
            "kor2",
            "hoth3",
            "hoth2",
            "academy1",
            "academy2",
            "academy3",
            "academy4",
            "academy5",
            "academy6"
        ],
        "mapTypePriority" : {
            "enabled" : true,
            "primary" : 2,
            "secondary" : 0,
            "nochange" : 1
        },
        "allowNominateCurrentMap" : false,
        "emptyServerMap" : 
        {
            "enabled" : true,
            "map" : "mb2_dotf_classicb"
        },
        "timeLimit" : 
        {
            "enabled" : false,
            "seconds" : 0
        },
        "roundLimit" : 
        {
            "enabled" : false,
            "rounds" : 0
        },
        "minimumVoteRatio" :
        {
            "enabled" : true,
            "percent" : 0.1
        },
        "successTimeout" : 30,
        "failureTimeout" : 60,
        "disableRecentlyPlayedMaps" : 1800,
        "skipVoting" : true,
        "secondTurnVoting" : true,
        "changeImmediately" : true
    },
    "rtm" : 
    {
        "enabled" : true,
        "voteTime" : 20,
        "voteAnnounceTimer" : 30,
        "voteRequiredRatio" : 0.5,
        "modes_enabled" : ["Open", "Legends", "Duel", "Full Authentic"],
        "emptyServerMode" : 
        {
            "enabled" : false,
            "mode" : "open"
        },
        "timeLimit" : 
        {
            "enabled" : false,
            "seconds" : 0
        },
        "roundLimit" : 
        {
            "enabled" : false,
            "rounds" : 0
        },
        "minimumVoteRatio" :
        {
            "enabled" : false,
            "percent" : 0
        },
        "successTimeout" : 60,
        "failureTimeout" : 60,
        "skipVoting" : true,
        "secondTurnVoting" : true,
        "changeImmediately" : true
    }
}

"""

MBMODE_ID_MAP = {
    'open' : 0,
    'semiauthentic' : 1,
    'fullauthentic' : 2,
    'duel' : 3,
    'legends' : 4
}

if DEFAULT_CFG == None:
    DEFAULT_CFG = config.Config()
    with open(DEFAULT_CFG_PATH, "wt") as f:
        f.write(CONFIG_FALLBACK)

Log = logging.getLogger(__name__);

class MapPriorityType(Enum):
    MAPTYPE_PRIMARY =  auto()
    MAPTYPE_SECONDARY = auto()
    MAPTYPE_NOCHANGE = auto()
    MAPTYPE_AUTO = auto()

class Map(object):
    def __init__(self, mapName, mapPath):
        self._mapName = mapName
        self._mapPath = mapPath
        self._priority = MapPriorityType.MAPTYPE_AUTO

    def GetMapName(self) -> str:
        return self._mapName
    
    def GetMapPath(self) -> str:
        return self._mapPath

    def GetPriority(self) -> int:
        return self._priority

    def SetPriority(self, val):
        if val in [MapPriorityType.MAPTYPE_NOCHANGE, MapPriorityType.MAPTYPE_PRIMARY, MapPriorityType.MAPTYPE_SECONDARY, MapPriorityType.MAPTYPE_AUTO]:
            self._priority = val
        
    def __str__(self):
        return "Map: " + self._mapName
    
    def __repr__(self):
        return self.__str__()

class MapContainer(object):
    def __init__(self, mapArray : list[Map], pluginInstance):
        self._mapCount = 0
        self._mapDict = {}
        primaryMapList = [x.lower() for x in pluginInstance._config.cfg["rtv"]["primaryMaps"]]
        secondaryMapList = [x.lower() for x in pluginInstance._config.cfg["rtv"]["secondaryMaps"]]
        mapBanList = [x.lower() for x in pluginInstance._config.cfg["rtv"]["mapBanList"]]
        useSecondaryMaps = pluginInstance._config.cfg["rtv"]["useSecondaryMaps"]
        automaticMaps = pluginInstance._config.cfg["rtv"]["automaticMaps"]
        if automaticMaps:
            for m in mapArray:
                m.SetPriority(MapPriorityType.MAPTYPE_AUTO)
                self._mapDict[m.GetMapName()] = m
        else:
            for m in mapArray:
                if m.GetMapName().lower() in primaryMapList:
                    m.SetPriority(MapPriorityType.MAPTYPE_PRIMARY)
                    self._mapDict[m.GetMapName()] = m
                elif m.GetMapName().lower() in secondaryMapList and useSecondaryMaps > 0:
                    m.SetPriority(MapPriorityType.MAPTYPE_SECONDARY)
                    self._mapDict[m.GetMapName()] = m
        for m in list(self._mapDict.keys()):
            mLower = m.lower()
            if (mLower in mapBanList):
                del self._mapDict[m]
        self._mapCount = len(self._mapDict.keys())
    
    def GetAllMaps(self) -> list[Map]:
        return list(self._mapDict.values())

    def GetMapCount(self) -> int:
        return self._mapCount

    def GetRandomMaps(self, num, blacklist=None) -> list[Map]:
        if blacklist != None:
            blacklist = [x.lower() for x in blacklist]
        valid_maps = [m for m in self._mapDict.values() if m.GetMapName().lower() not in blacklist]
        if len(valid_maps) < num:
            return valid_maps
        return sample(valid_maps, k=num)

    def FindMapWithName(self, name) -> Map | None:
        for m in self._mapDict:
            if m.lower() == name.lower():
                return self._mapDict[m]
        return None

class RTVVote(object):
    def __init__(self, voteOptions, voteTime=DEFAULT_CFG.cfg["rtv"]["voteTime"], announceCount = 1):
        self._voteOptions : list[Map] = voteOptions
        self._voteTime = voteTime
        self._voteStartTime = None
        self._playerVotes = {}
        self._announceTimer = Timeout()
    
    def  _Start(self):
        for i in range(len(self._voteOptions)):
            self._playerVotes[i+1] = []
        self._voteStartTime = time()

    def HandleVoter(self, voterId, voterOption):
        voteType = "rtm" if type(self) == RTMVote else "rtv"
        for i in self._playerVotes:
            if voterId in self._playerVotes[i]:
                self._playerVotes[i].remove(voterId)
        self._playerVotes[voterOption+1].append(voterId)
        if PluginInstance._config.cfg[voteType]["skipVoting"] == True:
            votesLeft = len(PluginInstance._serverData.API.GetAllClients()) - self.GetVoterCount()
            if len(self._playerVotes[voterOption+1]) > votesLeft:
                self._voteStartTime = 0     # instantly finish vote
        print(f"player {voterId} voted for {voterOption+1}")
        return True
    
    def GetOptions(self):
        return self._voteOptions

    def GetWinners(self):
        voteType = "rtm" if type(self) == RTMVote else "rtv"
        winners = []
        countMax = 0
        for i in self._playerVotes:
            if len(winners) == 0 or len(self._playerVotes[i]) > countMax:
                winners = [i]
                countMax = len(self._playerVotes[i])
            elif len(self._playerVotes[i]) == countMax:
                winners.append(i)
        # if second turn voting is enabled, allow a second winner if the first winner did not get at least 50% of the total voters
        if PluginInstance._config.cfg[voteType]["secondTurnVoting"] == True and len(winners) == 1 and len(self._playerVotes[winners[0]]) <= (self.GetVoterCount() // 2):
            sortedByVote = list(self._playerVotes)
            sortedByVote.sort(key = lambda a : len(self._playerVotes[a]))
            sortedByVote.reverse()  # list is initially sorted with lowest values first
            winners.append(sortedByVote[1])
        return [self._voteOptions[x - 1] for x in winners] if countMax > 0 else []

    def GetVoterCount(self):
        return sum([len(self._playerVotes[x]) for x in self._playerVotes])


class RTMVote(RTVVote):
    def __init__(self, voteOptions, voteTime=DEFAULT_CFG.cfg["rtm"]["voteTime"], announceCount=1):
        super().__init__(voteOptions, voteTime, announceCount)

class RTV(object):
    def __init__(self, serverData : serverdata.ServerData):
        self._config : config.Config = DEFAULT_CFG        
        self._themeColor = self._config.cfg["pluginThemeColor"]
        self._players : dict[player.Player] = {}
        self._serverData : serverdata.ServerData = serverData
        self._wantsToRTV : list[int] = []
        self._nominations : list[RTVNomination] = []
        self._currentVote = None
        self._messagePrefix : str = colors.COLOR_CODES[self._themeColor] + self._config.cfg["MessagePrefix"]
        self._mapContainer = MapContainer(GetAllMaps(), self)
        self._commandList = \
            {
                # commands and aliases must be tuples because lists are unhashable apparently
                # index 0 : tuple of aliases for each command
                # index 1: tuple of help string and handler function
                teams.TEAM_GLOBAL : {
                    tuple(["rtv", "rock the vote"]) : ("!<rtv | rock the vote> - vote to start the next Map vote", self.HandleRTV),
                    tuple(["rtm"]) : ("!rtm - vote to start the next RTM vote", self.HandleRTM),
                    tuple(["unrtm"]) : ("!unrtm - revoke your vote to start the next RTM vote", self.HandleUnRTM),
                    tuple(["unrtv", "unrockthevote"]) : ("!<unrtv | unrockthevote> - cancel your vote to start the next Map vote", self.HandleUnRTV),
                    tuple(["maplist"]) : ("!maplist <#> - display page # of the server's map list", self.HandleMaplist),
                    tuple(["nom", "nominate", "mapnom"]) : ("!nominate <map> - nominates a map for the next round of voting", self.HandleMapNom),
                    tuple(["search"]) : ("!search <query> - searches for the given query phrase in the map list", self.HandleSearch),
                    tuple(["1", "2", "3", "4", "5", "6"]) : ("", self.HandleDecimalVote)    # handle decimal votes (e.g !1, !2, !3)
                },
                teams.TEAM_EVIL : {
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote)    # handle decimal votes (e.g !1, !2, !3)
                },
                teams.TEAM_GOOD : {
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote)    # handle decimal votes (e.g !1, !2, !3)
                },
                teams.TEAM_SPEC : {
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote)    # handle decimal votes (e.g !1, !2, !3)
                }
            }
        self._smodCommandList = \
        {
            tuple(["frtv", "forcertv"]) : ("!<frtv | forcertv> - forces an RTV vote if no other vote is currently active", self.HandleForceRTV)
        }
        self._mapName = None
        self._wantsToRTM = []
        self._rtvCooldown = Timeout()
        self._rtmCooldown = Timeout()
        self._rtvRecentMaps : list[tuple(Map, Timeout)] = []
        self._rtvToSwitch = None
        self._rtmToSwitch = None
        self._roundTimer = 0
        if self._config.cfg["useSayOnly"] == True:
            self.SvSay = self.Say

    def Say(self, saystr):
        return self._serverData.interface.Say(self._messagePrefix + saystr)

    def SvSay(self, saystr):
        return self._serverData.interface.SvSay(self._messagePrefix + saystr)

    def _getAllPlayers(self):
        return self._players
    
    def _doLoop(self):
        # check vote status
        if self._currentVote != None:
            voteType = "rtm" if type(self._currentVote) == RTMVote else "rtv"
            if time() - self._currentVote._voteStartTime >= self._currentVote._voteTime:
                self._OnVoteFinish()
            elif self._currentVote._announceTimer.IsSet() == False:
                self._currentVote._announceTimer.Set(self._config.cfg[voteType]["voteAnnounceTimer"])
                self._AnnounceVote()
        # check recent map timers
        self._rtvRecentMaps = [i for i in self._rtvRecentMaps if i[1].IsSet()]

    def _AnnounceVote(self):
        saystr = ""
        for i in range(len(self._currentVote._voteOptions)):
            saystr += f"{i+1}({len(self._currentVote._playerVotes[i+1])}): {self._currentVote._voteOptions[i].GetMapName()}; "
        self.SvSay(saystr[:-2])
    
    def _OnVoteStart(self):
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress == None:
            self._serverData.SetServerVar("votesInProgress", ["RTV"])
        else:
            votesInProgress.append("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
    
    def _OnVoteFinish(self):
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        voteType = "rtm" if type(self._currentVote) == RTMVote else "rtv"
        if votesInProgress == None:
            self._serverData.SetServerVar("votesInProgress", [])
        elif "RTV" in votesInProgress:
            votesInProgress.remove("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
        # Check for vote percentage threshold if applicable
        if self._config.cfg[voteType]["minimumVoteRatio"]["enabled"] and (self._currentVote.GetVoterCount() / len(self._serverData.API.GetAllClients())) < self._config.cfg[voteType]["minimumVoteRatio"]["ratio"]:
            self.SvSay(f"Vote participation threshold was not met! (Needed {self._config.cfg[voteType]['minimumVoteRatio']['ratio'] * 100} percent)")
            self._currentVote = None
            if type(self._currentVote) == RTMVote:
                self._rtmCooldown.Set(self._config.cfg["rtm"]["failureTimeout"])
            else:
                self._rtvCooldown.Set(self._config.cfg["rtv"]["failureTimeout"])
            return None
        winners = self._currentVote.GetWinners()
        if voteType == "rtv" and not self._config.cfg["rtv"]["automaticMaps"] and self._config.cfg["rtv"]["mapTypePriority"]["enabled"]:
            # Attempt to resolve through priority
            priorityMap = {
                MapPriorityType.MAPTYPE_NOCHANGE : self._config.cfg["rtv"]["mapTypePriority"]["nochange"],
                MapPriorityType.MAPTYPE_PRIMARY : self._config.cfg["rtv"]["mapTypePriority"]["primary"],
                MapPriorityType.MAPTYPE_SECONDARY : self._config.cfg["rtv"]["mapTypePriority"]["secondary"],
            }
            maxPrio = max(winners, key=lambda a : priorityMap[a.GetPriority()]).GetPriority()
            winners = [winner for winner in winners if priorityMap[winner.GetPriority()] == priorityMap[maxPrio]]
        if len(winners) == 1:
            winner = winners[0]
            if winner.GetMapName() != "Don't Change":
                if type(self._currentVote) == RTMVote:
                    if self._config.cfg["rtm"]["changeImmediately"] == True:
                        self._SwitchRTM(winner)
                    else:
                        self._rtmToSwitch = winner
                        self.SvSay(f"Vote complete! Changing mode to {colors.ColorizeText(winner.GetMapName(), self._themeColor)} next round!")
                    self._rtmCooldown.Set(self._config.cfg["rtm"]["successTimeout"])
                else:
                    t = Timeout()
                    t.Set(self._config.cfg["rtv"]["disableRecentlyPlayedMaps"])
                    self._rtvRecentMaps.append((winner.GetMapName(), t))
                    if self._config.cfg["rtv"]["changeImmediately"] == True:
                        self._SwitchRTV(winner)
                    else:
                        self._rtvToSwitch = winner
                        self.SvSay(f"Vote complete! Changing map to {colors.ColorizeText(winner.GetMapName(), self._themeColor)} next round!")
                    self._rtvCooldown.Set(self._config.cfg["rtv"]["successTimeout"])
            else:
                if type(self._currentVote) == RTMVote:
                    self.SvSay(f"Voted to not change mode.");
                    self._rtmCooldown.Set(self._config.cfg["rtm"]["successTimeout"])
                else:
                    self.SvSay(f"Voted to not change map.");
                    self._rtvCooldown.Set(self._config.cfg["rtv"]["successTimeout"])
            self._currentVote = None
        elif len(winners) > 1:
            voteOptions = [winner for winner in winners]
            tiebreakerVote = RTVVote(voteOptions)
            if type(self._currentVote) == RTMVote:
                self._StartRTMVote(voteOptions)
            else:
                self._StartRTVVote(voteOptions)
        elif len(winners) == 0:
            self.SvSay("Vote ended with no voters, keeping everything the same!");
            # TODO: This will cause a crash with a vote with 0 options, shouldn't occur in practice
            if type(self._currentVote) == RTMVote:
                self._rtmCooldown.Set(self._config.cfg["rtm"]["failureTimeout"])
            else:
                self._rtvCooldown.Set(self._config.cfg["rtv"]["failureTimeout"])
            self._currentVote = None

    def _SwitchRTM(self, winner : Map, doSleep=True):
        self._rtmToSwitch = None
        modeToChange = MBMODE_ID_MAP[winner.GetMapName().lower().replace(' ', '')]
        self.SvSay(f"Switching game mode to {colors.ColorizeText(winner.GetMapName(), self._themeColor)}!")
        if doSleep:
            sleep(1)
        self._serverData.interface.MbMode(modeToChange)
    
    def _SwitchRTV(self, winner : Map, doSleep=True):
        self._rtvToSwitch = None
        mapToChange = winner.GetMapName()
        self.SvSay(f"Switching map to {colors.ColorizeText(mapToChange, self._themeColor)}!");
        #self._serverData.interface.SvSound("sound/sup/barney/ba_later.wav") -> Optionally uncomment for custom server sounds, << MBAssets4//OR//mb2_sup_assets/sound/sup >>
        #sleep(4)
        if doSleep:
            sleep(1)
        self._serverData.interface.MapReload(mapToChange);
    
    def HandleChatCommand(self, player : player.Player, teamId : int, cmdArgs : list[str]) -> bool:
        command = cmdArgs[0]
        for c in self._commandList[teamId]:
            if command in c:
                return self._commandList[teamId][c][1](player, teamId, cmdArgs)
        return False

    
    def HandleRTV(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if self._serverData.GetServerVar("campaignMode") == True:
                self.SvSay("RTV is disabled. !togglecampaign to vote to enable it!");
                return capture
            elif self._rtvCooldown.IsSet():
                self.SvSay(f"RTV is on cooldown for {colors.ColorizeText(self._rtvCooldown.LeftDHMS(), self._themeColor)}.")
                return capture
            if not eventPlayerId in self._wantsToRTV:
                self._wantsToRTV.append(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 wants to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already wants to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
            if len(self._wantsToRTV) >= ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio']):
                self._StartRTVVote()
        return capture

    def _StartRTVVote(self, choices=None):
        self._wantsToRTV.clear()
        voteChoices = []
        print("RTV start")
        if choices == None:
            blacklist = [x[0] for x in self._rtvRecentMaps]
            if self._config.cfg["rtv"]["useSecondaryMaps"] < 2:
                blacklist.extend([x.GetMapName() for x in self._mapContainer.GetAllMaps() if x.GetPriority() == MapPriorityType.MAPTYPE_SECONDARY])
            for nom in self._nominations:
                voteChoices.append(nom.GetMap())
            choices = self._mapContainer.GetRandomMaps(5 - len(self._nominations), blacklist=blacklist)
            while (self._mapName in [x.GetMapName() for x in choices] and self._config.cfg["rtv"]["allowNominateCurrentMap"] == True) or ((True in [x.GetMap() in choices for x in self._nominations]) and (not len(choices) <= self._mapContainer.GetMapCount())):
                choices = self._mapContainer.GetRandomMaps(5 - len(self._nominations), blacklist=blacklist)
            self._nominations.clear()
            voteChoices.extend([x for x in choices])
            noChangeMap = Map("Don't Change", "N/A")
            noChangeMap.SetPriority(MapPriorityType.MAPTYPE_NOCHANGE)
            voteChoices.append(noChangeMap)
        else:
            voteChoices = choices
        newVote = RTVVote(voteChoices)
        self._currentVote = newVote
        self._OnVoteStart()
        self._currentVote._Start()
        self.SvSay(f"{colors.ColorizeText('RTV', self._themeColor)} has started! Vote will complete in {colors.ColorizeText(str(self._currentVote._voteTime), self._themeColor)} seconds.")
        # self._AnnounceVote()

    def _StartRTMVote(self, choices=None):
        self._wantsToRTM.clear()
        voteChoices = []
        print("RTM start")
        if choices == None:
            choices = self._config.cfg["rtm"]["modes_enabled"]
            voteChoices.extend([Map(x, "RTM") for x in choices])
            noChangeMap = Map("Don't Change", "RTM")
            noChangeMap.SetPriority(MapPriorityType.MAPTYPE_NOCHANGE)
            voteChoices.append(noChangeMap)
        else:
            voteChoices = choices
        newVote = RTMVote(voteChoices)
        self._currentVote = newVote
        self._OnVoteStart()
        self._currentVote._Start()
        self.SvSay(f"{colors.ColorizeText('RTM', self._themeColor)} has started! Vote will complete in {colors.ColorizeText(str(self._currentVote._voteTime), self._themeColor)} seconds.")
        # self._AnnounceVote()

    def HandleRTM(self, player: player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if self._config.cfg["rtm"]["enabled"] == False:
                self.SvSay("This server has RTM disabled.");
                return capture
            elif self._rtmCooldown.IsSet():
                self.SvSay(f"RTM is on cooldown for {colors.ColorizeText(self._rtmCooldown.LeftDHMS(), self._themeColor)}.")
                return capture
            if not eventPlayerId in self._wantsToRTM:
                self._wantsToRTM.append(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 wants to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already wants to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
            if len(self._wantsToRTM) >= ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio']):
                self._StartRTMVote()
        return capture

    def HandleUnRTM(self, player: player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if eventPlayerId in self._wantsToRTM:
                self._wantsToRTM.remove(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 no longer wants to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already didn't want to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
        return capture
        

    def HandleUnRTV(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if self._serverData.GetServerVar("campaignMode") == True:
                self.SvSay("RTV is disabled. !togglecampaign to vote to enable it!")
                return capture
            if eventPlayerId in self._wantsToRTV:
                self._wantsToRTV.remove(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 no longer wants to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already doesn't want to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
        return capture

    def HandleMapNom(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = False
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and len(cmdArgs) >= 2:
            capture = True
            mapToNom = cmdArgs[1]
            playerHasNomination = eventPlayer in [x.GetPlayer() for x in self._nominations]
            if self._mapContainer.FindMapWithName(mapToNom) != None and len(self._nominations) < 5 and not self._mapContainer.FindMapWithName(mapToNom) in [x.GetMap() for x in self._nominations] and (self._config.cfg["rtv"]["allowNominateCurrentMap"] == False or (self._config.cfg["rtv"]["allowNominateCurrentMap"] == True and mapToNom != self._mapName)):
                mapObj = self._mapContainer.FindMapWithName(mapToNom)
                if playerHasNomination:
                    for i in self._nominations:
                        if i.GetPlayer() == eventPlayer:
                            self._nominations.remove(i)
                self._nominations.append(RTVNomination(eventPlayer, mapObj))
                if playerHasNomination:
                    self.SvSay(f"Player {eventPlayer.GetName()}^7 changed their nomination to {colors.ColorizeText(mapToNom, self._themeColor)}!")
                else:
                    self.SvSay(f"Player {eventPlayer.GetName()}^7 nominated {colors.ColorizeText(mapToNom, self._themeColor)} for RTV!")
            else:
                if not self._mapContainer.FindMapWithName(mapToNom):
                    failReason = "map was not found"
                elif len(self._nominations) >= 5:
                    failReason = "nomination list full"
                elif self._mapContainer.FindMapWithName(mapToNom) in [x.GetMap() for x in self._nominations]:
                    failReason = "map already nominated"
                elif (self._config.cfg["rtv"]["allowNominateCurrentMap"] == True and mapToNom == self._mapName):
                    failReason = "server does not allow nomination of current map"
                else:
                    failReason = "unknown reason"
                self.Say(f"Map could not be nominated: {failReason}")
        return capture

    def HandleMaplist(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = False
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if len(cmdArgs) == 2:
            capture = True
            pages = []
            pageStr = ""
            for map in self._mapContainer.GetAllMaps():
                if len(pageStr) < 950:
                    pageStr += map.GetMapName()
                    pageStr += ', '
                else:
                    pageStr = pageStr[:-2]
                    pages.append(pageStr)
                    pageStr = ""
                    pageStr += map.GetMapName()
                    pageStr += ', '
            pages.append(pageStr[:-2])
            if cmdArgs[1].isdecimal():
                pageIndex = int(cmdArgs[1])
                if 1 <= pageIndex <= len(pages):
                    self.Say(pages[pageIndex - 1])
                else:
                    self.Say(f"Index out of range! (1-{len(pages)})")
            else:
                self.Say(f"Invalid index {colors.ColorizeText(cmdArgs[1], self._themeColor)}!")
        return capture

    def HandleSearch(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = False
        if len(cmdArgs) > 1:
            searchQuery = ' '.join(cmdArgs[1:])
            totalResults = 0
            mapPages = []
            mapStr = ""
            for map in self._mapContainer.GetAllMaps():
                mapName = map.GetMapName()
                if all(str.find(mapName, x) != -1 for x in cmdArgs[1:]):
                    for searchTerm in cmdArgs[1:]:
                        index = str.find(mapName, searchTerm)
                        mapName = colors.HighlightSubstr(mapName, index, index + len(searchTerm), self._themeColor)
                    if len(mapStr) + len(mapName) < 950:
                        mapStr += mapName
                        mapStr += ', '
                    else:
                        mapStr = mapStr[:-2]
                        mapPages.append(mapStr)
                        mapStr = mapName + ', '
                    totalResults += 1
            if len(mapStr) > 0:
                mapPages.append(mapStr[:-2])
            if len(mapPages) == 0:
                self._serverData.interface.SvTell(player.GetId(), f"{self._messagePrefix} Search {colors.ColorizeText(searchQuery, self._themeColor)} returned no results.")
            elif len(mapPages) == 1:
                self.Say(f"{str(totalResults)} results for {colors.ColorizeText(searchQuery, self._themeColor)}: {mapPages[0]}")
            elif len(mapPages) > 1:
                # mapPages.reverse()
                batchCmds = [f"say {self._messagePrefix}{str(totalResults)} result(s) for {colors.ColorizeText(searchQuery, self._themeColor)}:"]
                batchCmds += [f"say {self._messagePrefix}{x}" for x in mapPages]
                self._serverData.interface.BatchExecute("b", batchCmds, sleepBetweenChunks=0.1)
        return capture

    def HandleDecimalVote(self, player : player.Player, teamId : int, cmdArgs : list[str]) -> bool:
        capture = False
        currVote = self._currentVote
        if currVote != None:
            if cmdArgs[0].isdecimal():
                capture = True
                index = int(cmdArgs[0])-1;
                if index in range(0, len(currVote.GetOptions())):
                    currVote.HandleVoter(player, index);
        return capture

    def OnChatMessage(self, eventClient : client.Client, eventMessage : str, eventTeamID : int):
        if eventClient != None:
            Log.debug(f"Received chat message from client {eventClient.GetId()}")
            commandPrefix = self._config.cfg["RTVPrefix"]
            capture = False
            eventPlayer : player.Player = self._players[eventClient.GetId()]
            eventPlayerId = eventPlayer.GetId()
            currentVote = self._currentVote
            votesInProgress = self._serverData.GetServerVar("votesInProgress")
            eventMessage = eventMessage.lower()
            if eventPlayer != None:
                capture : bool = False;
                if eventMessage.startswith(self._config.cfg["RTVPrefix"]) or not self._config.cfg["requirePrefix"]:
                    if eventMessage.startswith(self._config.cfg["RTVPrefix"]):
                        eventMessage = eventMessage[len(self._config.cfg["RTVPrefix"]):]
                    if len ( eventMessage ) > 0: # in case if someone sends just a prefix and nothing else, otherwise we're splitting an empty string
                        messageParse = eventMessage.split()
                        return self.HandleChatCommand(eventPlayer, eventTeamID, messageParse)
                return capture;
            return False
    
    def OnClientConnect(self, eventClient : client.Client):
        newPlayer = Player(eventClient)
        self._OnNewPlayer(newPlayer);
        return False

    def _OnNewPlayer(self, newPlayer : player.Player):
        newPlayerId = newPlayer.GetId()
        if newPlayerId in self._players:
            Log.warning(f"Player ID {newPlayerId} already exists in RTV players. Overwriting entry with newly connected player's data...")
        self._players[newPlayerId] = newPlayer

    def OnClientDisconnect(self, eventClient : client.Client, reason : int):
        if reason != godfingerEvent.ClientDisconnectEvent.REASON_SERVER_SHUTDOWN:
            dcPlayerId = eventClient.GetId()
            if dcPlayerId in self._players:
                del self._players[dcPlayerId]
            else:
                Log.warning(f"Player ID {dcPlayerId} does not exist in RTV players but there was an attempt to remove it")
        return False
    
    def OnEmptyServer(self, data, isStartup):
        doMap = self._config.cfg["rtv"]["emptyServerMap"]["enabled"]
        doMode = self._config.cfg["rtm"]["emptyServerMode"]["enabled"]
        if doMap and doMode:
            self._serverData.interface.MbMode(MBMODE_ID_MAP[self._config.cfg["rtm"]["emptyServerMode"]["mode"]], self._config.cfg["rtv"]["emptyServerMap"]["map"])
        elif doMap:
            self._serverData.interface.MapReload(self._config.cfg["rtv"]["emptyServerMap"]["map"])
        elif doMode:
            self._serverData.interface.MbMode(MBMODE_ID_MAP[self._config.cfg["rtm"]["emptyServerMode"]["mode"]])
        return False

    def OnClientChange(self, eventClient, eventData):
        return False

    def OnServerInit(self, data):
        self._roundTimer += 1
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not self._currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if self._config.cfg["rtv"]["roundLimit"]["enabled"] == True and self._roundTimer > self._config.cfg["rtv"]["roundLimit"]["rounds"]:
                self._StartRTVVote()
                self._roundTimer = 0
            elif self._config.cfg["rtm"]["roundLimit"]["enabled"] == True and self._roundTimer > self._config.cfg["rtm"]["roundLimit"]["rounds"]:
                self._StartRTMVote()
                self._roundTimer = 0
        # self._SwitchRT* sets their corresponding ToSwitch variable to None
        if self._rtvToSwitch != None:
            self._SwitchRTV(self._rtvToSwitch)
        elif self._rtmToSwitch != None:
            self._SwitchRTM(self._rtmToSwitch)
        return False

    def OnServerShutdown(self):
        return False

    def OnClientKill(self, eventClient, eventVictim, eventWeaponStr):
        return False

    def OnPlayer(self, client, data):
        return False

    def OnExit(self, eventData):
        return False
    
    def OnMapChange(self, mapName, oldMapName) -> bool:
        Log.debug(f"Map change event received: {mapName}")
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if "RTV" in votesInProgress:
            votesInProgress.remove("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
        if mapName != self._mapName:
            self._mapName = mapName
        if self._currentVote != None:
            self._currentVote = None
        return False

    def HandleForceRTV(self, playerName, smodId, adminIP, cmdArgs):
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if self._serverData.GetServerVar("campaignMode") == True:
                self.SvSay("RTV is disabled. !togglecampaign to vote to enable it!")
                return True
            else:
                self.SvSay("Smod forced RTV vote")
                self._StartRTVVote()
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
    
    def Start(self) -> bool:
        allClients = self._serverData.API.GetAllClients();
        for cl in allClients:
            newPlayer = player.Player(cl);
            self._OnNewPlayer(newPlayer);
        return True;


    def OnSmsay(self, senderName : str, smodID : int, senderIP : str, message : str):
        message = message.lower()
        messageParse = message.split()
        return self.HandleSmodCommand(senderName, smodID, senderIP, messageParse)

class RTVNomination(object):
    def __init__(self, player, map):
        self._player = player
        self._map = map

    def GetPlayer(self) -> player.Player:
        return self._player

    def GetMap(self) -> Map:
        return self._map

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    startTime = time()
    serverMap = PluginInstance._serverData.mapName;
    if serverMap == '': # godfinger hasn't initialized map yet, we gotta get it straight from the server
        serverMap = PluginInstance._serverData.interface.GetCvar("mapname")
    PluginInstance._mapName = serverMap
    if not PluginInstance.Start():
        return False;
    if PluginInstance._config.cfg["kickProtectedNames"] == True:
        for i in PluginInstance._serverData.API.GetAllClients():
            nameStripped = colors.StripColorCodes(i.GetName().lower())
            if nameStripped == "admin" or nameStripped == "server":
                PluginInstance._serverData.interface.ClientKick(i.GetId())
    loadTime = time() - startTime
    PluginInstance._serverData.interface.Say(PluginInstance._messagePrefix + f"RTV started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    PluginInstance._doLoop()
    #print("Calling Loop function from plugin!");

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    global PluginInstance
    del PluginInstance;

# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports=None):
    global SERVER_DATA;
    SERVER_DATA = serverData;

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

    global PluginInstance;
    PluginInstance = RTV(serverData)
    

    if exports != None:
        exports.Add("StartRTVVote", API_StartRTVVote)
    
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for i in cmd:
            if not i.isdecimal():
                newVal.append((i, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newVal)
    return True; # indicate plugin load success

def API_StartRTVVote():
    Log.debug("Received external RTV vote request")
    global PluginInstance
    # currentVote = PluginInstance._voteContext.GetCurrentVote()
    votesInProgress = PluginInstance._serverData.GetServerVar("votesInProgress")
    if not PluginInstance._currentVote and (votesInProgress == None or len(votesInProgress) == 0):
        if PluginInstance._serverData.GetServerVar("campaignMode") == True:
            PluginInstance._serverData.rcon.svsay(PluginInstance._messagePrefix + "RTV is disabled. !togglecampaign to vote to enable it!")
            return False
        else:
            # PluginInstance._serverData.rcon.svsay(PluginInstance._messagePrefix + "External RTV vote")
            PluginInstance._StartRTVVote()
            return True
    return False

def OnEvent(event) -> bool:
    global PluginInstance;
    #print("Calling OnEvent function from plugin with event %s!" % (str(event)));
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return PluginInstance.OnChatMessage( event.client, event.message, event.teamId );
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return PluginInstance.OnClientConnect( event.client);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return PluginInstance.OnClientChange( event.client, event.data );
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return PluginInstance.OnClientDisconnect( event.client, event.reason );
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return PluginInstance.OnServerInit(event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return PluginInstance.OnServerShutdown();
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return PluginInstance.OnClientKill(event.client, event.victim, event.weaponStr);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return PluginInstance.OnPlayer(event.client, event.data["text"] if "text" in event.data else "");
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return PluginInstance.OnExit(event.data);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return PluginInstance.OnMapChange(event.mapName, event.oldMapName);
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SERVER_EMPTY:
        return PluginInstance.OnEmptyServer(event.data, event.isStartup)    
    return False

# Helper function to get all map names from currently installed PK3 files located in MBII directory and base directory next to MBII
def GetAllMaps() -> list[Map]:
    mbiiDir = DEFAULT_CFG.cfg["MBIIPath"] + "\\"
    mapList = []
    dirsToProcess = [mbiiDir, os.path.normpath(os.path.join(mbiiDir, "../base"))]; # base comes next so it wont override MBII dir contents if files match
    for dir in dirsToProcess:
        for filename in os.listdir(dir):
            if filename.endswith(".pk3"):
                with ZipFile(dir + "\\" + filename) as file:
                    zipNameList = file.namelist()
                    for name in zipNameList:
                        if name.endswith(".bsp") and not name in [x.GetMapName() for x in mapList]:
                            path = name
                            name = name.lower().removeprefix("maps/").removesuffix(".bsp")
                            newMap = Map(name, path)
                            #Log.debug(str(path));
                            mapList.append(newMap)
    return mapList
