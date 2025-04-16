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
from lib.shared.colors import ColorizeText, HighlightSubstr
from lib.shared.player import Player
from lib.shared.timeout import Timeout

SERVER_DATA = None

DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "rtvConfig.json");
DEFAULT_CFG = config.Config.fromJSON(DEFAULT_CFG_PATH)

CONFIG_FALLBACK = \
"""{
    "mapBanList" : 
    [
        "fifa",
        "tmnt",
        "SOM_ptf_Sdestroyer",
        "SOM_Sdestroyer",
        "SOM_theed",
        "pb2_citadel",
        "pb2_cloudcity",
        "pb2_ctf_bespin",
        "pb2_ctf_imperial",
        "pb2_ctf_rift",
        "pb2_ctf_theed",
        "pb2_dotf",
        "pb2_kashyyyk",
        "pb2_ptf_jeditemple",
        "pb2_ptf_sdestroyer",
        "pb2_reactor",
        "pb2_sdestroyer",
        "pb_dotf",
        "pb_sdestroyer",
        "som_dotf",
        "som_snowfacility",
        "pb3_reactor",
        "uM_Canyon_guns",
        "uM_Taspir_rockets",
        "uM_birdmino",
        "uM_crazyrace2",
        "um_bouncy",
        "um_crazyrace",
        "um_ctf_gib_bespin",
        "um_ctf_gib_coruscant",
        "um_ctf_gib_narshaddaa",
        "um_ctf_gib_narshaddaa",
        "um_football",
        "um_jawarace",
        "um_nightmare",
        "um_prisonraid_v4",
        "um_rockettennis",
        "um_rockettennis",
        "um_spacerace",
        "um_swooprace",
        "um_xwing",
        "mb2_sailbarge",
        "mb2_veh_destroyer"
    ],
    "mapBanListWhitelist" : false,
    
    "emptyServerMap" : 
    {
        "enabled" : true,
        "map" : "gc_intermission"
    },
    
    "successTimeout" : 1800,
    "failureTimeout" : 60,
    "enableRecentlyPlayedMaps" : 1800,

    "MBIIPath": "your/mbii/path/here",
    "MessagePrefix": "^5[RTV]^7: ",
    "RTVPrefix": "!",
    "requirePrefix" : false,
    "allowNominateCurrentMap" : false,
    "voteTime" : 20,

    "rtm" : 
    {
        "enabled" : true,
        "modes_enabled" : ["Open", "Legends", "Duel", "Full Authentic"],
        "successTimeout" : 60,
        "failureTimeout" : 60
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
    DEFAULT_CFG.cfg = json.loads(CONFIG_FALLBACK)
    f = open(DEFAULT_CFG_PATH, "wt")
    f.write(CONFIG_FALLBACK)
    f.close()

Log = logging.getLogger(__name__);

class Map(object):
    def __init__(self, mapName, mapPath):
        self._mapName = mapName
        self._mapPath = mapPath

    def GetMapName(self) -> str:
        return self._mapName
    
    def GetMapPath(self) -> str:
        return self._mapPath
        
    def __str__(self):
        return "Map: " + self._mapName
    
    def __repr__(self):
        return self.__str__()

class MapContainer(object):
    def __init__(self, mapArray : list[Map], pluginInstance):
        self._mapCount = 0
        self._mapDict = {}
        mapBanList = pluginInstance._config.cfg["mapBanList"]
        for m in mapArray:
            self._mapDict[m.GetMapName()] = m
        for m in list(self._mapDict.keys()):
            mLower = m.lower()
            if (mLower in mapBanList and pluginInstance._config.cfg["mapBanListWhitelist"] == False) \
            or (mLower not in mapBanList and pluginInstance._config.cfg["mapBanListWhitelist"] == True):
                del self._mapDict[m]
        self._mapCount = len(self._mapDict.keys())
    
    def GetAllMaps(self) -> list[Map]:
        return list(self._mapDict.values())

    def GetMapCount(self) -> int:
        return self._mapCount

    def GetRandomMaps(self, num, blacklist=None) -> list[Map]:
        if num > self._mapCount:
            return sample(list(self._mapDict.values()), k=self._mapCount)
        elif num < 0:
            return []
        else:
            return sample(list(self._mapDict.values()), k=num)

    def FindMapWithName(self, name) -> Map | None:
        for m in self._mapDict:
            if m == name:
                return self._mapDict[m]
        return None

class RTVVote(object):
    def __init__(self, voteOptions, voteTime=DEFAULT_CFG.cfg["voteTime"], announceCount = 1):
        self._voteOptions : list[Map] = voteOptions
        self._voteTime = voteTime
        self._voteStartTime = None
        self._voteThreshold = 0.5
        self._playerVotes = {}
        self._hasAnnounced = False
    
    def  _Start(self):
        for i in range(len(self._voteOptions)):
            self._playerVotes[i+1] = []
        self._voteStartTime = time()

    def HandleVoter(self, voterId, voterOption):
        for i in self._playerVotes:
            if voterId in self._playerVotes[i]:
                self._playerVotes[i].remove(voterId)
        self._playerVotes[voterOption+1].append(voterId)
        print(f"player {voterId} voted for {voterOption+1}")
        return True
    
    def GetOptions(self):
        return self._voteOptions

    def GetWinners(self):
        winners = []
        countMax = 0
        for i in self._playerVotes:
            if len(winners) == 0 or len(self._playerVotes[i]) > countMax:
                winners = [i]
                countMax = len(self._playerVotes[i])
            elif len(self._playerVotes[i]) == countMax:
                winners.append(i)
        return [self._voteOptions[x - 1] for x in winners] if countMax > 0 else []

class RTMVote(RTVVote):
    def __init__(self, voteOptions, voteTime=DEFAULT_CFG.cfg["voteTime"], announceCount=1):
        super().__init__(voteOptions, voteTime, announceCount)

class RTV(object):
    def __init__(self, serverData : serverdata.ServerData):
        self._config : config.Config = DEFAULT_CFG        
        self._players : dict[player.Player] = {}
        self._serverData : serverdata.ServerData = serverData
        self._wantsToRTV : list[int] = []
        self._nominations : list[RTVNomination] = []
        self._voteThreshold : int = 0.5
        self._currentVote = None
        self._messagePrefix : str = self._config.cfg["MessagePrefix"]
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
        self._rtvRecentMap = None
        self._rtvRecentMapTimeout = Timeout()

    def _getAllPlayers(self):
        return self._players
    
    def _doLoop(self):
        if self._currentVote != None:
            if time() - self._currentVote._voteStartTime >= self._currentVote._voteTime:
                self._OnVoteFinish()
            elif floor(time()) % 30 == 0 and not self._currentVote._hasAnnounced:
                self._currentVote._hasAnnounced = True
                self._AnnounceVote()

    def _AnnounceVote(self):
        saystr = ""
        for i in range(len(self._currentVote._voteOptions)):
            saystr += f"{i+1}({len(self._currentVote._playerVotes[i+1])}): {self._currentVote._voteOptions[i].GetMapName()}; "
        self._serverData.interface.SvSay(self._messagePrefix + saystr[:-2])
    
    def _OnVoteStart(self):
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress == None:
            self._serverData.SetServerVar("votesInProgress", ["RTV"])
        else:
            votesInProgress.append("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
    
    def _OnVoteFinish(self):
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress == None:
            self._serverData.SetServerVar("votesInProgress", [])
        else:
            if "RTV" in votesInProgress:
                votesInProgress.remove("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
        winners = self._currentVote.GetWinners()
        if len(winners) == 1:
            winner = winners[0]
            if winner.GetMapName() != "Don't Change":
                if type(self._currentVote) == RTMVote:
                    modeToChange = MBMODE_ID_MAP[winner.GetMapName().lower().replace(' ', '')]
                    self._serverData.interface.SvSay(self._messagePrefix + f"Switching game mode to {winner.GetMapName()}!")
                    sleep(1)
                    self._serverData.interface.MbMode(modeToChange)
                    self._rtmCooldown.Set(self._config.cfg["rtm"]["successTimeout"])
                else:
                    mapToChange = winner.GetMapName()
                    self._serverData.interface.SvSay(self._messagePrefix + f"Switching map to {mapToChange}!");
                    sleep(1)
                    self._serverData.interface.MapReload(mapToChange);
                    self._rtvCooldown.Set(self._config.cfg["successTimeout"])
            else:
                if type(self._currentVote) == RTMVote:
                    self._serverData.interface.SvSay(self._messagePrefix + f"Voted to not change mode.");
                    self._rtmCooldown.Set(self._config.cfg["rtm"]["successTimeout"])
                else:
                    self._serverData.interface.SvSay(self._messagePrefix + f"Voted to not change map.");
                    self._rtvCooldown.Set(self._config.cfg["successTimeout"])
            self._currentVote = None
        elif len(winners) > 1:
            voteOptions = [winner for winner in winners]
            tiebreakerVote = RTVVote(voteOptions)
            if type(self._currentVote) == RTMVote:
                self._StartRTMVote(voteOptions)
            else:
                self._StartRTVVote(voteOptions)
        elif len(winners) == 0:
            self._serverData.interface.SvSay(self._messagePrefix + "Vote ended with no votes, keeping everything the same!");
            # TODO: This will cause a crash with a vote with 0 options, shouldn't occur in practice
            if type(self._currentVote) == RTMVote:
                self._rtmCooldown.Set(self._config.cfg["rtm"]["failureTimeout"])
            else:
                self._rtvCooldown.Set(self._config.cfg["failureTimeout"])
    
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
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if self._serverData.GetServerVar("campaignMode") == True:
                self._serverData.interface.SvSay(self._messagePrefix + "RTV is disabled. !togglecampaign to vote to enable it!");
                return capture
            elif self._rtvCooldown.IsSet():
                self._serverData.interface.SvSay(self._messagePrefix + f"RTV is on cooldown for {ColorizeText(self._rtvCooldown.LeftDHMS(), 'lblue')}.")
                return capture
            if not eventPlayerId in self._wantsToRTV:
                self._wantsToRTV.append(eventPlayerId)
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 wants to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._voteThreshold)})")
            else:
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 already wants to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._voteThreshold)})")
            if len(self._wantsToRTV) >= ceil(len(self._players) * self._voteThreshold):
                self._StartRTVVote()
        return capture

    def _StartRTVVote(self, choices=None):
        self._wantsToRTV.clear()
        voteChoices = []
        print("RTV start")
        if choices == None:
            for nom in self._nominations:
                voteChoices.append(nom.GetMap())
            choices = self._mapContainer.GetRandomMaps(5 - len(self._nominations))
            while (self._mapName in [x.GetMapName() for x in choices] and self._config.cfg["allowNominateCurrentMap"] == True) or ((True in [x.GetMap() in choices for x in self._nominations]) and (not len(choices) <= self._mapContainer.GetMapCount())):
                choices = self._mapContainer.GetRandomMaps(5 - len(self._nominations))
            self._nominations.clear()
            voteChoices.extend([x for x in choices])
            voteChoices.append(Map("Don't Change", "N/A"))
        else:
            voteChoices = choices
        newVote = RTVVote(voteChoices)
        self._currentVote = newVote
        self._OnVoteStart()
        self._currentVote._Start()
        self._serverData.interface.SvSay(self._messagePrefix + f"{ColorizeText('RTV', 'lblue')} has started! Vote will complete in {ColorizeText(str(self._currentVote._voteTime), 'lblue')} seconds.")
        self._AnnounceVote()

    def _StartRTMVote(self, choices=None):
        self._wantsToRTM.clear()
        voteChoices = []
        print("RTM start")
        if choices == None:
            choices = self._config.cfg["rtm"]["modes_enabled"]
            voteChoices.extend([Map(x, "RTM") for x in choices])
            voteChoices.append(Map("Don't Change", "RTM"))
        else:
            voteChoices = choices
        newVote = RTMVote(voteChoices)
        self._currentVote = newVote
        self._OnVoteStart()
        self._currentVote._Start()
        self._serverData.interface.SvSay(self._messagePrefix + f"{ColorizeText('RTM', 'lblue')} has started! Vote will complete in {ColorizeText(str(self._currentVote._voteTime), 'lblue')} seconds.")
        self._AnnounceVote()

    def HandleRTM(self, player: player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if self._config.cfg["rtm"]["enabled"] == False:
                self._serverData.interface.SvSay(self._messagePrefix + "This server has RTM disabled.");
                return capture
            elif self._rtmCooldown.IsSet():
                self._serverData.interface.SvSay(self._messagePrefix + f"RTM is on cooldown for {ColorizeText(self._rtmCooldown.LeftDHMS(), 'lblue')}.")
                return capture
            if not eventPlayerId in self._wantsToRTM:
                self._wantsToRTM.append(eventPlayerId)
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 wants to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._voteThreshold)})")
            else:
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 already wants to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._voteThreshold)})")
            if len(self._wantsToRTM) >= ceil(len(self._players) * self._voteThreshold):
                self._StartRTMVote()
        return capture

    def HandleUnRTM(self, player: player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if eventPlayerId in self._wantsToRTM:
                self._wantsToRTM.remove(eventPlayerId)
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 no longer wants to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._voteThreshold)})")
            else:
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 already didn't want to RTM! ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._voteThreshold)})")
        return capture
        

    def HandleUnRTV(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if self._serverData.GetServerVar("campaignMode") == True:
                self._serverData.interface.SvSay(self._messagePrefix + "RTV is disabled. !togglecampaign to vote to enable it!")
                return capture
            if eventPlayerId in self._wantsToRTV:
                self._wantsToRTV.remove(eventPlayerId)
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 no longer wants to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._voteThreshold)})")
            else:
                self._serverData.interface.SvSay(self._messagePrefix + f"{eventPlayer.GetName()}^7 already doesn't want to RTV! ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._voteThreshold)})")
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
            if self._mapContainer.FindMapWithName(mapToNom) != None and len(self._nominations) < 5 and not self._mapContainer.FindMapWithName(mapToNom) in [x.GetMap() for x in self._nominations] and not playerHasNomination and (self._config.cfg["allowNominateCurrentMap"] == False or (self._config.cfg["allowNominateCurrentMap"] == True and mapToNom != self._mapName)):
                mapObj = self._mapContainer.FindMapWithName(mapToNom)
                self._nominations.append(RTVNomination(eventPlayer, mapObj))
                self._serverData.interface.SvSay(self._messagePrefix + f"Player {eventPlayer.GetName()}^7 nominated {mapToNom} for RTV!")
            else:
                if not self._mapContainer.FindMapWithName(mapToNom):
                    failReason = "map was not found"
                elif len(self._nominations) >= 5:
                    failReason = "nomination list full"
                elif self._mapContainer.FindMapWithName(mapToNom) in [x.GetMap() for x in self._nominations]:
                    failReason = "map already nominated"
                elif playerHasNomination:
                    failReason = "player has already nominated map"
                elif (self._config.cfg["allowNominateCurrentMap"] == True and mapToNom == self._mapName):
                    failReason = "server does not allow nomination of current map"
                else:
                    failReason = "unknown reason"
                self._serverData.interface.Say(self._messagePrefix + f"Map could not be nominated: {failReason}")
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
                    self._serverData.interface.Say(self._messagePrefix + pages[pageIndex - 1])
                else:
                    self._serverData.interface.Say(self._messagePrefix + f"Index out of range! (1-{len(pages)})")
            else:
                self._serverData.interface.Say(self._messagePrefix + f"Invalid index ^2{cmdArgs[1]}^7!")
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
                        mapName = HighlightSubstr(mapName, index, index + len(searchTerm), "lblue")
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
                self._serverData.interface.SvTell(player.GetId(), self._messagePrefix + f"Search ^5{searchQuery}^7 returned no results.")
            elif len(mapPages) == 1:
                self._serverData.interface.Say(self._messagePrefix + f"{str(totalResults)} results for ^5{searchQuery}^7: {mapPages[0]}")
            elif len(mapPages) > 1:
                # mapPages.reverse()
                batchCmds = [f"say {self._messagePrefix}{str(totalResults)} results for ^5{searchQuery}^7:"]
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
    
    def OnClientChange(self, eventClient, eventData):
        return False

    def OnServerInit(self, data):
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
                self._serverData.interface.SvSay(self._messagePrefix + "RTV is disabled. !togglecampaign to vote to enable it!")
                return True
            else:
                self._serverData.interface.SvSay(self._messagePrefix + "Smod forced RTV vote")
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
    global PluginInstance
    currentVote = PluginInstance._voteContext.GetCurrentVote()
    votesInProgress = PluginInstance._serverData.GetServerVar("votesInProgress")
    if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
        if PluginInstance._serverData.GetServerVar("campaignMode") == True:
            PluginInstance._serverData.rcon.svsay(PluginInstance._messagePrefix + "RTV is disabled. !togglecampaign to vote to enable it!")
            return False
        else:
            PluginInstance._serverData.rcon.svsay(PluginInstance._messagePrefix + "Smod forced RTV vote")
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
    return False

# Helper function to get all map names from currently installed PK3 files located in MBII directory and base directory next to MBII
def GetAllMaps() -> list[Map]:
    mbiiDir = DEFAULT_CFG.cfg["MBIIPath"]
    mapList = []
    dirsToProcess = [mbiiDir, os.path.normpath(os.path.join(mbiiDir, "../base"))]; # base comes next so it wont override MBII dir contents if files match
    for dir in dirsToProcess:
        for filename in os.listdir(dir):
            if filename.endswith(".pk3"):
                with ZipFile(dir + "\\" + filename) as file:
                    zipNameList = file.namelist()
                    for name in zipNameList:
                        if name.endswith(".bsp") and not name in mapList:
                            path = name
                            name = name.lower().removeprefix("maps/").removesuffix(".bsp")
                            newMap = Map(name, path)
                            #Log.debug(str(path));
                            mapList.append(newMap)
    return mapList
