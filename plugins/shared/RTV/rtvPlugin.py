# ORIGINAL RTVRTM SCRIPT CREDITS:
# =================================================================================
# Copyright (c) 2012-2013, klax / Cthulhu@GBITnet.com.br
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

#################################################
#          Movie Battles II RTV/RTM             #
#                                               #
#      Rock the Vote and Rock the Mode tool     #
#      for Jedi Knight: Jedi Academy            #
#      Movie Battles II MOD.                    #
#      Original plugin and idea by:             #
#      AlliedModders LLC. All rights reserved.  #
#################################################
# =================================================================================
# GODFINGER RTV CREDITS:
# =================================================================================
# Godfinger contributors:
# 2cwldys (https://github.com/2cwldys),
# ACHUTA/Mantlar, (https://github.com/mantlar)
# ViceDice, (https://github.com/ViceDice)
# Wookiee- (https://github.com/Wookiee-)
#
# RTV plugin created by ACHUTA



from enum import Enum, auto
import json
import logging
import os
import re
from math import ceil, floor
from random import sample
from time import sleep, time
from zipfile import ZipFile

# Import Godfinger Event system and shared libraries
import godfingerEvent
import lib.shared.client as client
import lib.shared.config as config
import lib.shared.player as player
import lib.shared.serverdata as serverdata
import lib.shared.teams as teams
import lib.shared.colors as colors
from lib.shared.player import Player
from lib.shared.timeout import Timeout

Log = logging.getLogger(__name__)

# Global server data instance
SERVER_DATA = None

# Configuration file paths and defaults
DEFAULT_CFG_PATH = os.path.join(os.path.dirname(__file__), "rtvConfig.json")
DEFAULT_CFG = config.Config.fromJSON(DEFAULT_CFG_PATH)

# Fallback configuration if config file doesn't exist
CONFIG_FALLBACK = \
"""{
    "MBIIPath": "your/mbii/path/here",
    "pluginThemeColor" : "green",
    "MessagePrefix": "[RTV]^7: ",
    "RTVPrefix": "!",
    "caseSensitiveCommands" : false,
    "requirePrefix" : false,
    "protectedNames" : ["admin", "server"],
    "kickProtectedNames" : true,
    "useSayOnly" : false,
    "floodProtection" :
    {
        "enabled" : false,
        "soft" : false,
        "seconds" : 1.5
    },
    "showVoteCooldownTime" : 5,
    "maxMapPageSize" : 950,
    "maxSearchPageSize" : 950,
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
            "ratio" : 0.1
        },
        "successTimeout" : 30,
        "failureTimeout" : 60,
        "disableRecentlyPlayedMaps" : 1800,
        "disableRecentMapNomination" : true,
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
            "ratio" : 0
        },
        "successTimeout" : 60,
        "failureTimeout" : 60,
        "skipVoting" : true,
        "secondTurnVoting" : true,
        "changeImmediately" : true
    }
}

"""

# Map game modes to their internal IDs
MBMODE_ID_MAP = {
    'open' : 0,
    'semiauthentic' : 1,
    'fullauthentic' : 2,
    'duel' : 3,
    'legends' : 4
}

# Create default config if it doesn't exist
if DEFAULT_CFG == None:
    DEFAULT_CFG = config.Config()
    DEFAULT_CFG.cfg = json.loads(CONFIG_FALLBACK)
    Log.error(f"Could not open config file at {os.path.dirname(__file__) + 'rtvConfig.json, ensure the file is a valid JSON file in the correct file path.'}")
    with open(DEFAULT_CFG_PATH, "wt") as f:
        f.write(CONFIG_FALLBACK)

# Initialize logger

class MapPriorityType(Enum):
    """Enumeration for map priority types"""
    MAPTYPE_PRIMARY =  auto()
    MAPTYPE_SECONDARY = auto()
    MAPTYPE_NOCHANGE = auto()
    MAPTYPE_AUTO = auto()

class Map(object):
    """Represents a game map with name, path, and priority"""
    def __init__(self, mapName, mapPath):
        self._mapName = mapName
        self._mapPath = mapPath
        self._priority = MapPriorityType.MAPTYPE_AUTO

    def GetMapName(self) -> str:
        """Get map name"""
        return self._mapName
    
    def GetMapPath(self) -> str:
        """Get map file path"""
        return self._mapPath

    def GetPriority(self) -> int:
        """Get map priority type"""
        return self._priority

    def SetPriority(self, val):
        """Set map priority type"""
        if val in [MapPriorityType.MAPTYPE_NOCHANGE, MapPriorityType.MAPTYPE_PRIMARY, MapPriorityType.MAPTYPE_SECONDARY, MapPriorityType.MAPTYPE_AUTO]:
            self._priority = val
        
    def __str__(self):
        return "Map: " + self._mapName
    
    def __repr__(self):
        return self.__str__()

class MapContainer(object):
    """Container for managing available maps with filtering and prioritization"""
    def __init__(self, mapArray : list[Map], pluginInstance):
        self._mapCount = 0
        self._mapDict = {}
        self._pages = []
        self.plugin : RTV = pluginInstance
        
        # Get configuration from plugin instance
        primaryMapList = [x.lower() for x in self.plugin._config.cfg["rtv"]["primaryMaps"]]
        secondaryMapList = [x.lower() for x in self.plugin._config.cfg["rtv"]["secondaryMaps"]]
        mapBanList = [x.lower() for x in self.plugin._config.cfg["rtv"]["mapBanList"]]
        useSecondaryMaps = self.plugin._config.cfg["rtv"]["useSecondaryMaps"]
        automaticMaps = self.plugin._config.cfg["rtv"]["automaticMaps"]
        
        # Process maps based on configuration
        if automaticMaps:
            # Include all maps with auto priority
            for m in mapArray:
                m.SetPriority(MapPriorityType.MAPTYPE_AUTO)
                self._mapDict[m.GetMapName()] = m
        else:
            # Filter maps based on primary/secondary lists
            for m in mapArray:
                if m.GetMapName().lower() in primaryMapList:
                    m.SetPriority(MapPriorityType.MAPTYPE_PRIMARY)
                    self._mapDict[m.GetMapName()] = m
                elif m.GetMapName().lower() in secondaryMapList and useSecondaryMaps > 0:
                    m.SetPriority(MapPriorityType.MAPTYPE_SECONDARY)
                    self._mapDict[m.GetMapName()] = m
        
        # Apply ban list
        for m in list(self._mapDict.keys()):
            mLower = m.lower()
            if (mLower in mapBanList):
                del self._mapDict[m]
        
        self._mapCount = len(self._mapDict.keys())
        self._CreatePages()
    
    def GetAllMaps(self) -> list[Map]:
        """Get all available maps"""
        return list(self._mapDict.values())

    def GetMapCount(self) -> int:
        """Get total number of available maps"""
        return self._mapCount

    def GetRandomMaps(self, num, blacklist=None) -> list[Map]:
        """Get random selection of maps excluding blacklisted ones"""
        # Convert blacklist to lowercase for case-insensitive matching
        if blacklist is not None:
            blacklist = [x.lower() for x in blacklist]
        else:
            blacklist = []
            
        # Get all available maps that are not blacklisted
        available_maps = []
        for m in self._mapDict.values():
            if m.GetMapName().lower() not in blacklist:
                available_maps.append(m)
        
        # Handle edge cases
        if num <= 0:
            return []
        if num > len(available_maps):
            return available_maps
        
        # Return random selection
        return sample(available_maps, k=num)

    def FindMapWithName(self, name) -> Map | None:
        """Find map by name (case-insensitive)"""
        name_lower = name.lower()
        for m in self._mapDict:
            if m.lower() == name_lower:
                return self._mapDict[m]
        return None

    def _CreatePages(self) -> None:
        """Generate cached pages for map list"""
        pages = []
        pageStr = ""
        for map in self._mapDict.values():
            if len(pageStr) < self.plugin._config.cfg["maxMapPageSize"]:
                pageStr += map.GetMapName() + ", "
            else:
                pageStr = pageStr[:-2]
                pages.append(pageStr)
                pageStr = map.GetMapName() + ", "
        if len(pageStr) > 2:
            pages.append(pageStr[:-2])
        self._pages = pages
    
    def GetPageCount(self) -> int:
        """Get total number of pages"""
        return len(self._pages)

class RTVVote(object):
    """Base class for handling voting systems (RTV and RTM)"""
    def __init__(self, voteOptions, voteTime=DEFAULT_CFG.cfg["rtv"]["voteTime"], announceCount = 1):
        self._voteOptions : list[Map] = voteOptions
        self._voteTime = voteTime
        self._voteStartTime = None
        self._playerVotes = {}
        self._announceTimer = Timeout()
    
    def  _Start(self):
        """Initialize vote tracking"""
        for i in range(len(self._voteOptions)):
            self._playerVotes[i+1] = []
        self._voteStartTime = time()

    def HandleVoter(self, voterId, voterOption):
        """Process a player's vote"""
        voteType = "rtm" if type(self) == RTMVote else "rtv"
        
        # Remove previous vote if exists
        for i in self._playerVotes:
            if voterId in self._playerVotes[i]:
                self._playerVotes[i].remove(voterId)
        
        # Record new vote
        self._playerVotes[voterOption+1].append(voterId)
        
        # Skip voting if enabled and majority reached
        if PluginInstance._config.cfg[voteType]["skipVoting"] == True:
            votesLeft = len(PluginInstance._serverData.API.GetAllClients()) - self.GetVoterCount()
            if len(self._playerVotes[voterOption+1]) > votesLeft:
                self._voteStartTime = 0  # instantly finish vote
        print(f"player {voterId} voted for {voterOption+1}")
        return True
    
    def GetOptions(self):
        """Get available vote options"""
        return self._voteOptions

    def GetWinners(self):
        """Determine vote winner(s) with tie resolution"""
        voteType = "rtm" if type(self) == RTMVote else "rtv"
        winners = []
        countMax = 0
        
        # Find option(s) with highest votes
        for i in self._playerVotes:
            if len(winners) == 0 or len(self._playerVotes[i]) > countMax:
                winners = [i]
                countMax = len(self._playerVotes[i])
            elif len(self._playerVotes[i]) == countMax:
                winners.append(i)
        
        # Handle second turn voting if enabled
        if PluginInstance._config.cfg[voteType]["secondTurnVoting"] == True and \
           len(winners) == 1 and \
           len(self._playerVotes[winners[0]]) <= (self.GetVoterCount() // 2):
            sortedByVote = list(self._playerVotes)
            sortedByVote.sort(key = lambda a : len(self._playerVotes[a]))
            sortedByVote.reverse()  # list is initially sorted with lowest values first
            winners.append(sortedByVote[1])
        
        return [self._voteOptions[x - 1] for x in winners] if countMax > 0 else []

    def GetVoterCount(self):
        """Get total number of voters"""
        return sum([len(self._playerVotes[x]) for x in self._playerVotes])


class RTMVote(RTVVote):
    """Specialized vote class for Rock the Mode (RTM)"""
    def __init__(self, voteOptions, voteTime=DEFAULT_CFG.cfg["rtm"]["voteTime"], announceCount=1):
        super().__init__(voteOptions, voteTime, announceCount)

class RTVPlayer(player.Player):
    """ Specialized player class for RTV/RTM, implements RTV/RTM specific player variables  """
    def __init__(self, cl: client.Client):
        super().__init__(cl)
        self._floodProtectionCooldown = Timeout()
        self._lastCommand = None

class RTV(object):
    """Main class implementing Rock the Vote (RTV) and Rock the Mode (RTM) functionality"""
    def __init__(self, serverData : serverdata.ServerData):
        # Configuration setup
        self._config : config.Config = DEFAULT_CFG
        self._themeColor = self._config.cfg["pluginThemeColor"]
        self._players : dict[int, RTVPlayer] = {}
        self._serverData : serverdata.ServerData = serverData
        
        # RTV state tracking
        self._wantsToRTV : list[int] = []
        self._nominations : list[RTVNomination] = []
        self._currentVote = None
        
        # Message formatting
        self._messagePrefix : str = colors.COLOR_CODES[self._themeColor] + self._config.cfg["MessagePrefix"]
        
        # Map management
        self._mapContainer = MapContainer(GetAllMaps(), self)
        
        # Command definitions
        self._commandList = \
            {
                # Global commands
                teams.TEAM_GLOBAL : {
                    ("rtv", "rockthevote") : ("!<rtv | rock the vote> - vote to start the next Map vote", self.HandleRTV),
                    ("rtm", "rockthemode") : ("!rtm - vote to start the next RTM vote", self.HandleRTM),
                    ("unrtm", "unrockthemode") : ("!unrtm - revoke your vote to start the next RTM vote", self.HandleUnRTM),
                    ("unrtv", "unrockthevote") : ("!<unrtv | unrockthevote> - cancel your vote to start the next Map vote", self.HandleUnRTV),
                    ("maplist", "maps") : ("!maplist <#> - display page # of the server's map list", self.HandleMaplist),
                    ("nom", "nominate", "mapnom") : ("!nominate <map> - nominates a map for the next round of voting", self.HandleMapNom),
                    ("nomlist", "nominationlist", "nominatelist", "noml") : ("!nomlist - displays a list of nominations for the next map", self.HandleNomList),
                    ("search", "mapsearch") : ("!search <query> - searches for the given query phrase in the map list", self.HandleSearch),
                    ('help', "cmds") : ("!help - display help about a given command, or all commands if no command is given", self.HandleHelp),
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote),  # handle decimal votes
                    ("showvote", "showrtv") : ("!showvote - shows the current vote stats if a vote is active", self.HandleShowVote)
                },
                # Team-specific commands (only vote commands for other teams)
                teams.TEAM_EVIL : {
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote)
                },
                teams.TEAM_GOOD : {
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote)
                },
                teams.TEAM_SPEC : {
                    ("1", "2", "3", "4", "5", "6") : ("", self.HandleDecimalVote)
                }
            }
        
        # Server Moderator commands
        self._smodCommandList = \
        {
            ("frtv", "forcertv") : ("!<frtv | forcertv> - forces an RTV vote if no other vote is currently active", self.HandleForceRTV),
            ("frtm", "forcertm") : ("!<frtm | forcertm> - forces an RTM vote if no other vote is currently active", self.HandleForceRTM),
            ("rtvenable", "rtve") : ("!rtvenable - finishes the timeout period of RTV immediately", self.HandleRTVEnable),
            ("rtmenable", "rtme") : ("!rtmenable - finishes the timeout period of RTM immediately", self.HandleRTMEnable)
        }
        
        # State tracking variables
        self._mapName = None
        self._wantsToRTM = []
        self._rtvCooldown = Timeout()
        self._rtmCooldown = Timeout()
        self._rtvRecentMaps : list[tuple(Map, Timeout)] = []
        self._rtvToSwitch = None
        self._rtmToSwitch = None
        self._roundTimer = 0
        self._announceCooldown = Timeout()
        
        # Configure say method based on settings
        if self._config.cfg["useSayOnly"] == True:
            self.SvSay = self.Say

    def Say(self, saystr : str, usePrefix : bool = True):
        """Send console message to all players"""
        prefix = self._messagePrefix if usePrefix else ""
        return self._serverData.interface.Say(prefix + saystr)

    def SvSay(self, saystr : str, usePrefix : bool = True):
        """Send chat message to all players"""
        prefix = self._messagePrefix if usePrefix else ""
        return self._serverData.interface.SvSay(prefix + saystr)
    
    def SvTell(self, pid: int, saystr : str, usePrefix : bool = True):
        """Send chat message to one player given their ID"""
        prefix = self._messagePrefix if usePrefix else ""
        return self._serverData.interface.SvTell(pid, prefix + saystr)

    def _getAllPlayers(self):
        """Get all connected players"""
        return self._players
    
    def _doLoop(self):
        """Main loop processing for vote management"""
        # Check vote status
        if self._currentVote != None:
            voteType = "rtm" if type(self._currentVote) == RTMVote else "rtv"
            
            # Check if vote time has expired
            if time() - self._currentVote._voteStartTime >= self._currentVote._voteTime:
                self._OnVoteFinish()
            # Announce vote status at intervals
            elif self._currentVote._announceTimer.IsSet() == False:
                self._currentVote._announceTimer.Set(self._config.cfg[voteType]["voteAnnounceTimer"])
                self._AnnounceVote()
        
        # Clean up expired recent maps
        self._rtvRecentMaps = [i for i in self._rtvRecentMaps if i[1].IsSet()]

    def _AnnounceVote(self):
        """Announce current vote status to all players"""
        saystr = ""
        for i in range(len(self._currentVote._voteOptions)):
            saystr += f"{i+1}({len(self._currentVote._playerVotes[i+1])}): {self._currentVote._voteOptions[i].GetMapName()}; "
        self.SvSay(saystr[:-2])
    
    def _OnVoteStart(self):
        """Handle vote start event"""
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress == None:
            self._serverData.SetServerVar("votesInProgress", ["RTV"])
        else:
            votesInProgress.append("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
    
    def _OnVoteFinish(self):
        """Process vote results and determine next action"""
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        voteType = "rtm" if type(self._currentVote) == RTMVote else "rtv"
        
        # Clean up vote tracking
        if votesInProgress == None:
            self._serverData.SetServerVar("votesInProgress", [])
        elif "RTV" in votesInProgress:
            votesInProgress.remove("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
        
        # Check vote participation threshold
        if self._config.cfg[voteType]["minimumVoteRatio"]["enabled"] and \
           len(self._serverData.API.GetAllClients()) > 0 and \
           (self._currentVote.GetVoterCount() / len(self._serverData.API.GetAllClients())) < \
           self._config.cfg[voteType]["minimumVoteRatio"]["ratio"]:
            self.SvSay(f"Vote participation threshold was not met! (Needed {self._config.cfg[voteType]['minimumVoteRatio']['ratio'] * 100} percent)")
            self._currentVote = None
            # Set appropriate cooldown
            if type(self._currentVote) == RTMVote:
                self._rtmCooldown.Set(self._config.cfg["rtm"]["failureTimeout"])
            else:
                self._rtvCooldown.Set(self._config.cfg["rtv"]["failureTimeout"])
            return None
        
        # Determine winner(s)
        winners = self._currentVote.GetWinners()
        
        # Apply map priority system for RTV votes
        if voteType == "rtv" and not self._config.cfg["rtv"]["automaticMaps"] and \
           self._config.cfg["rtv"]["mapTypePriority"]["enabled"]:
            priorityMap = {
                MapPriorityType.MAPTYPE_NOCHANGE : self._config.cfg["rtv"]["mapTypePriority"]["nochange"],
                MapPriorityType.MAPTYPE_PRIMARY : self._config.cfg["rtv"]["mapTypePriority"]["primary"],
                MapPriorityType.MAPTYPE_SECONDARY : self._config.cfg["rtv"]["mapTypePriority"]["secondary"],
            }
            maxPrio = max(winners, key=lambda a : priorityMap[a.GetPriority()]).GetPriority()
            winners = [winner for winner in winners if priorityMap[winner.GetPriority()] == priorityMap[maxPrio]]
        
        # Handle vote results
        if len(winners) == 1:
            winner = winners[0]
            if winner.GetMapName() != "Don't Change":
                if type(self._currentVote) == RTMVote:
                    # Handle RTM result
                    if self._config.cfg["rtm"]["changeImmediately"] == True:
                        self._SwitchRTM(winner)
                    else:
                        self._rtmToSwitch = winner
                        self.SvSay(f"Vote complete! Changing mode to {colors.ColorizeText(winner.GetMapName(), self._themeColor)} next round!")
                    self._rtmCooldown.Set(self._config.cfg["rtm"]["successTimeout"])
                else:
                    # Handle RTV result
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
                # Handle "Don't Change" result
                if type(self._currentVote) == RTMVote:
                    self.SvSay(f"Voted to not change mode.")
                    self._rtmCooldown.Set(self._config.cfg["rtm"]["successTimeout"])
                else:
                    self.SvSay(f"Voted to not change map.")
                    self._rtvCooldown.Set(self._config.cfg["rtv"]["successTimeout"])
            self._currentVote = None
        elif len(winners) > 1:
            # Handle tie - start tiebreaker vote
            voteOptions = [winner for winner in winners]
            if type(self._currentVote) == RTMVote:
                self._StartRTMVote(voteOptions)
            else:
                self._StartRTVVote(voteOptions)
        elif len(winners) == 0:
            # Handle no votes cast
            self.SvSay("Vote ended with no voters, keeping everything the same!")
            if type(self._currentVote) == RTMVote:
                self._rtmCooldown.Set(self._config.cfg["rtm"]["failureTimeout"])
            else:
                self._rtvCooldown.Set(self._config.cfg["rtv"]["failureTimeout"])
            self._currentVote = None

    def _SwitchRTM(self, winner : Map, doSleep=True):
        """Switch game mode to winner of RTM vote"""
        self._rtmToSwitch = None
        modeToChange = MBMODE_ID_MAP[winner.GetMapName().lower().replace(' ', '')]
        self.SvSay(f"Switching game mode to {colors.ColorizeText(winner.GetMapName(), self._themeColor)}!")
        if doSleep:
            sleep(1)
        self._serverData.interface.MbMode(modeToChange)
    
    def _SwitchRTV(self, winner : Map, doSleep=True):
        """Switch map to winner of RTV vote"""
        self._rtvToSwitch = None
        mapToChange = winner.GetMapName()
        self.SvSay(f"Switching map to {colors.ColorizeText(mapToChange, self._themeColor)}!")
        if doSleep:
            sleep(1)
        self._serverData.interface.MapReload(mapToChange)
    
    def HandleChatCommand(self, player : RTVPlayer, teamId : int, cmdArgs : list[str]) -> bool:
        """Route chat command to appropriate handler"""
        command = cmdArgs[0]
        if self._config.cfg["caseSensitiveCommands"] == False:
            command = command.lower()
        for c in self._commandList[teamId]:
            if command in c:
                if self._config.cfg["floodProtection"]["enabled"] == True:
                    if player._floodProtectionCooldown.IsSet() == True and \
                    ((self._config.cfg["floodProtection"]["soft"] == True and c == player._lastCommand) or self._config.cfg["floodProtection"]["soft"] == False):
                        return False
                    player._floodProtectionCooldown.Set(self._config.cfg["floodProtection"]["seconds"])
                    player._lastCommand = c
                return self._commandList[teamId][c][1](player, teamId, cmdArgs)
        return False

    # Command handlers below with detailed explanations
    
    def HandleRTV(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !rtv command - player votes to start map vote"""
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        
        # Check if RTV is possible
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            # Cooldown check
            if self._rtvCooldown.IsSet():
                self.SvSay(f"RTV is on cooldown for {colors.ColorizeText(self._rtvCooldown.LeftDHMS(), self._themeColor)}.")
                return capture
            
            # Process RTV request
            if not eventPlayerId in self._wantsToRTV:
                self._wantsToRTV.append(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 wants to {colors.ColorizeText('Rock the Vote!', self._themeColor)} ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already wants to {colors.ColorizeText('Rock the Vote!', self._themeColor)} ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
            
            # Check if threshold reached to start vote
            if len(self._wantsToRTV) >= ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio']):
                self._StartRTVVote()
        return capture

    def _StartRTVVote(self, choices=None, allowNoChange=True):
        """Start Rock the Vote process"""
        self._wantsToRTV.clear()
        voteChoices = []
        print("RTV start")
        
        # Build vote options if not provided
        if choices == None:
            # Prepare blacklist of maps to exclude
            blacklist = [x[0] for x in self._rtvRecentMaps]
            if self._config.cfg["rtv"]["useSecondaryMaps"] < 2:
                blacklist.extend([x.GetMapName() for x in self._mapContainer.GetAllMaps() if x.GetPriority() == MapPriorityType.MAPTYPE_SECONDARY])
            if not self._config.cfg["rtv"]["allowNominateCurrentMap"]:
                blacklist.append(self._mapName.lower())
                
            # Add nominated maps
            for nom in self._nominations:
                voteChoices.append(nom.GetMap())
                
            # Get random maps to fill options
            choices = self._mapContainer.GetRandomMaps(5 - len(self._nominations), blacklist=blacklist)
            
            # Filter out nominations to prevent duplicates
            nomination_names = {n.GetMap().GetMapName().lower() for n in self._nominations}
            choices = [m for m in choices if m.GetMapName().lower() not in nomination_names]
            
            # Clear nominations and build final list
            self._nominations.clear()
            voteChoices.extend([x for x in choices])
            
            # Add "Don't Change" option
            if allowNoChange == True:
                noChangeMap = Map("Don't Change", "N/A")
                noChangeMap.SetPriority(MapPriorityType.MAPTYPE_NOCHANGE)
                voteChoices.append(noChangeMap)
        else:
            voteChoices = choices
        
        # Create and start vote
        newVote = RTVVote(voteChoices)
        self._currentVote = newVote
        self._OnVoteStart()
        self._currentVote._Start()
        self.SvSay(f"{colors.ColorizeText('RTV', self._themeColor)} has started! Vote will complete in {colors.ColorizeText(str(self._currentVote._voteTime), self._themeColor)} seconds.")

    def _StartRTMVote(self, choices=None):
        """Start Rock the Mode process"""
        self._wantsToRTM.clear()
        voteChoices = []
        print("RTM start")
        
        # Build vote options if not provided
        if choices == None:
            choices = self._config.cfg["rtm"]["modes_enabled"]
            voteChoices.extend([Map(x, "RTM") for x in choices])
            
            # Add "Don't Change" option
            noChangeMap = Map("Don't Change", "RTM")
            noChangeMap.SetPriority(MapPriorityType.MAPTYPE_NOCHANGE)
            voteChoices.append(noChangeMap)
        else:
            voteChoices = choices
        
        # Create and start vote
        newVote = RTMVote(voteChoices)
        self._currentVote = newVote
        self._OnVoteStart()
        self._currentVote._Start()
        self.SvSay(f"{colors.ColorizeText('RTM', self._themeColor)} has started! Vote will complete in {colors.ColorizeText(str(self._currentVote._voteTime), self._themeColor)} seconds.")

    def HandleRTM(self, player: player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !rtm command - player votes to start mode vote"""
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        
        # Check if RTM is possible
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            # Feature enabled check
            if self._config.cfg["rtm"]["enabled"] == False:
                self.SvSay("This server has RTM disabled.")
                return capture
            # Cooldown check
            elif self._rtmCooldown.IsSet():
                self.SvSay(f"RTM is on cooldown for {colors.ColorizeText(self._rtmCooldown.LeftDHMS(), self._themeColor)}.")
                return capture
            
            # Process RTM request
            if not eventPlayerId in self._wantsToRTM:
                self._wantsToRTM.append(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 wants to {colors.ColorizeText('Rock the Mode!', self._themeColor)} ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already wants to {colors.ColorizeText('Rock the Mode!', self._themeColor)} ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
            
            # Check if threshold reached to start vote
            if len(self._wantsToRTM) >= ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio']):
                self._StartRTMVote()
        return capture

    def HandleUnRTM(self, player: player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !unrtm command - revoke RTM vote"""
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        
        # Check if revocation is possible
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if eventPlayerId in self._wantsToRTM:
                self._wantsToRTM.remove(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 no longer wants to {colors.ColorizeText('Rock the Mode!', self._themeColor)} ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already doesn't want to {colors.ColorizeText('Rock the Mode!', self._themeColor)} ({len(self._wantsToRTM)}/{ceil(len(self._players) * self._config.cfg['rtm']['voteRequiredRatio'])})")
        return capture
        

    def HandleUnRTV(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !unrtv command - revoke RTV vote"""
        capture = True
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        
        # Check if revocation is possible
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            # Process revocation
            if eventPlayerId in self._wantsToRTV:
                self._wantsToRTV.remove(eventPlayerId)
                self.SvSay(f"{eventPlayer.GetName()}^7 no longer wants to {colors.ColorizeText('Rock the Vote!', self._themeColor)} ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
            else:
                self.SvSay(f"{eventPlayer.GetName()}^7 already doesn't want to {colors.ColorizeText('Rock the Vote!', self._themeColor)} ({len(self._wantsToRTV)}/{ceil(len(self._players) * self._config.cfg['rtv']['voteRequiredRatio'])})")
        return capture

    def HandleMapNom(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !nominate command - nominate a map for voting"""
        capture = False
        eventPlayer = player
        eventPlayerId = eventPlayer.GetId()
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        
        # Check if nomination is possible
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0) and len(cmdArgs) >= 2:
            capture = True
            mapToNom = cmdArgs[1]
            playerHasNomination = eventPlayer in [x.GetPlayer() for x in self._nominations]
            
            # Validate nomination
            if self._mapContainer.FindMapWithName(mapToNom) != None and \
               len(self._nominations) < 5 and \
               not self._mapContainer.FindMapWithName(mapToNom) in [x.GetMap() for x in self._nominations] and \
                (self._config.cfg["rtv"]["allowNominateCurrentMap"] == False or mapToNom != self._mapName) and \
                (not mapToNom in [x[0] for x in self._rtvRecentMaps] or self._config.cfg["rtv"]["disableRecentMapNomination"] == False):
               
                mapObj = self._mapContainer.FindMapWithName(mapToNom)
                # Update existing nomination
                if playerHasNomination:
                    for i in self._nominations:
                        if i.GetPlayer() == eventPlayer:
                            self._nominations.remove(i)
                # Add new nomination
                self._nominations.append(RTVNomination(eventPlayer, mapObj))
                
                # Send appropriate message
                if playerHasNomination:
                    self.SvSay(f"Player {eventPlayer.GetName()}^7 changed their nomination to {colors.ColorizeText(mapToNom, self._themeColor)}!")
                else:
                    self.SvSay(f"Player {eventPlayer.GetName()}^7 nominated {colors.ColorizeText(mapToNom, self._themeColor)} for RTV!")
            else:
                # Handle invalid nomination
                if not self._mapContainer.FindMapWithName(mapToNom):
                    failReason = "map was not found"
                elif len(self._nominations) >= 5:
                    failReason = "nomination list full"
                elif self._mapContainer.FindMapWithName(mapToNom) in [x.GetMap() for x in self._nominations]:
                    failReason = "map already nominated"
                elif (self._config.cfg["rtv"]["allowNominateCurrentMap"] == True and mapToNom == self._mapName):
                    failReason = "server does not allow nomination of current map"
                elif (mapToNom in [x[0] for x in self._rtvRecentMaps] and self._config.cfg["rtv"]["disableRecentMapNomination"] == True):
                    failReason = "cannot nominate recently played map"
                else:
                    failReason = "unknown reason"
                self.Say(f"Map could not be nominated: {failReason}")
        return capture

    def HandleMaplist(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !maplist command - show available maps"""
        capture = False
        if len(cmdArgs) == 1:
            # Show usage message with total pages
            num_pages = self._mapContainer.GetPageCount()
            self.SvTell(player.GetId(), f"Usage: {colors.ColorizeText('!maplist <page>', self._themeColor)}, valid pages {colors.ColorizeText('1-' + str(num_pages), self._themeColor)}")
            capture = True
        elif len(cmdArgs) == 2:
            capture = True
            # Get page from cached pages
            try:
                page_index = int(cmdArgs[1]) - 1
                if page_index < 0:
                    raise ValueError
                if page_index >= len(self._mapContainer._pages):
                    self.SvSay(f"Index out of range! (1-{len(self._mapContainer._pages)})")
                else:
                    self.SvSay(self._mapContainer._pages[page_index])
            except (ValueError, IndexError):
                self.SvSay(f"Invalid index {colors.ColorizeText(cmdArgs[1], self._themeColor)}!")
        return capture

    def HandleSearch(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        """Handle !search command - search maps by name"""
        capture = False
        if len(cmdArgs) > 1:
            searchQuery = ' '.join(cmdArgs[1:])
            totalResults = 0
            mapPages = []
            mapStr = ""
            
            # Search maps
            for map in self._mapContainer.GetAllMaps():
                mapName = map.GetMapName()
                # Check if map matches all search terms
                if all(str.find(mapName, x) != -1 for x in cmdArgs[1:]):
                    # Highlight search terms in results
                    for searchTerm in cmdArgs[1:]:
                        index = str.find(mapName, searchTerm)
                        mapName = colors.HighlightSubstr(mapName, index, index + len(searchTerm), self._themeColor)
                    
                    # Add to results page
                    if len(mapStr) + len(mapName) < self._config.cfg["maxSearchPageSize"]:
                        mapStr += mapName
                        mapStr += ', '
                    else:
                        mapStr = mapStr[:-2]
                        mapPages.append(mapStr)
                        mapStr = mapName + ', '
                    totalResults += 1
            
            # Add remaining results
            if len(mapStr) > 0:
                mapPages.append(mapStr[:-2])
            
            # Display results
            if len(mapPages) == 0:
                self.SvTell(player.GetId(), f"Search {colors.ColorizeText(searchQuery, self._themeColor)} returned no results.")
            elif len(mapPages) == 1:
                self.Say(f"{str(totalResults)} results for {colors.ColorizeText(searchQuery, self._themeColor)}: {mapPages[0]}")
            elif len(mapPages) > 1:
                # Batch output for multiple pages
                batchCmds = [f"say {self._messagePrefix}{str(totalResults)} result(s) for {colors.ColorizeText(searchQuery, self._themeColor)}:"]
                batchCmds += [f"say {self._messagePrefix}{x}" for x in mapPages]
                self._serverData.interface.BatchExecute("b", batchCmds, sleepBetweenChunks=0.1)
        else:
            self.SvTell(player.GetId(), f"Usage: {colors.ColorizeText('!search <searchterm1> [searchterm2] [...]', self._themeColor)}")
        return capture

    def HandleDecimalVote(self, player : player.Player, teamId : int, cmdArgs : list[str]) -> bool:
        """Handle numeric voting commands (1-6) during active votes"""
        capture = False
        currVote = self._currentVote
        if currVote != None:
            if cmdArgs[0].isdecimal():
                capture = True
                index = int(cmdArgs[0])-1
                # Validate vote option
                if index in range(0, len(currVote.GetOptions())):
                    currVote.HandleVoter(player, index)
        return capture

    def HandleNomList(self, player : player.Player, teamId : int, cmdArgs : list[str]) -> bool:
        """Handle nomination list command"""
        capture = False
        outputStr = ""
        for i in self._nominations:
            outputStr += f"{i.GetMap().GetMapName()} ({i.GetPlayer().GetName()})^7;"
        if len(outputStr) > 0:
            self.Say(f"{colors.ColorizeText('Map Nominations', self._themeColor)}: " + outputStr)
        else:
            self.Say("No map nominations to display.")
        return capture

    def HandleShowVote(self, player : player.Player, teamId : int, cmdArgs : list[str]) -> bool:
        """ Handle show vote command """
        if not self._announceCooldown.IsSet():
            self._announceCooldown.Set(self._config.cfg["showVoteCooldownTime"])
            if self._currentVote != None:
                self._AnnounceVote()
            else:
                self.Say(f"No vote to display. Type {colors.ColorizeText('!rtv', self._themeColor)} in chat to {colors.ColorizeText('Rock the Vote', self._themeColor)}!")

    # only included if not already defined in another plugin
    def HandleHelp(self, player : player.Player, teamId : int, cmdArgs : list[str]):
        capture = True
        commandAliasList = self._serverData.GetServerVar("registeredCommands")
        if len(cmdArgs) > 1:
            for i in commandAliasList:
                if cmdArgs[1] == i[0]:
                    saystr = i[1]
                    self.Say(saystr)
                    return capture
            # couldn't find command
            self.Say(f"Couldn't find chat command {colors.ColorizeText(cmdArgs[1], self._themeColor)}")
        else:
            saystr = ', '.join([x[0] for x in commandAliasList])
            self.Say(colors.ColorizeText("(Say !help <command> for help on a specific command): ", self._themeColor) + saystr)
        return capture
        
    def OnChatMessage(self, eventClient : client.Client, eventMessage : str, eventTeamID : int):
        """Handle incoming chat messages and route commands"""
        if eventClient != None:
            Log.debug(f"Received chat message from client {eventClient.GetId()}")
            commandPrefix = self._config.cfg["RTVPrefix"]
            capture = False
            eventPlayer : RTVPlayer = self._players[eventClient.GetId()]
            eventPlayerId = eventPlayer.GetId()
            
            if eventPlayer != None:
                capture : bool = False
                # Check if message starts with command prefix
                if eventMessage.startswith(self._config.cfg["RTVPrefix"]) or not self._config.cfg["requirePrefix"]:
                    # Remove prefix if present
                    if eventMessage.startswith(self._config.cfg["RTVPrefix"]):
                        eventMessage = eventMessage[len(self._config.cfg["RTVPrefix"]):]
                    
                    # Process command if non-empty
                    if len ( eventMessage ) > 0:
                        messageParse = eventMessage.split()
                        return self.HandleChatCommand(eventPlayer, eventTeamID, messageParse)
            return capture
    
    def OnClientConnect(self, eventClient : client.Client):
        """Handle new client connection"""
        newPlayer = RTVPlayer(eventClient)
        self._OnNewPlayer(newPlayer)
        return False

    def _OnNewPlayer(self, newPlayer : player.Player):
        """Add new player to tracking"""
        newPlayerId = newPlayer.GetId()
        if newPlayerId in self._players:
            Log.warning(f"Player ID {newPlayerId} already exists in RTV players. Overwriting entry with newly connected player's data...")
        self._players[newPlayerId] = newPlayer

    def OnClientDisconnect(self, eventClient : client.Client, reason : int):
        """Handle client disconnection"""
        if reason != godfingerEvent.ClientDisconnectEvent.REASON_SERVER_SHUTDOWN:
            dcPlayerId = eventClient.GetId()
            dcPlayer = self._players[dcPlayerId]
            if dcPlayerId in self._players:
                if dcPlayerId in self._wantsToRTV:
                    self._wantsToRTV.remove(dcPlayerId)
                if dcPlayerId in self._wantsToRTM:
                    self._wantsToRTM.remove(dcPlayerId)
                for nom in self._nominations:
                    if nom.GetPlayer().GetId() == dcPlayerId:
                        self._nominations.remove(nom)
                del self._players[dcPlayerId]
                if self._currentVote != None:
                    for i in self._currentVote._playerVotes:
                        if dcPlayerId in self._currentVote._playerVotes[i]:
                            self._currentVote._playerVotes[i].remove(dcPlayerId)
            else:
                Log.warning(f"Player ID {dcPlayerId} does not exist in RTV players but there was an attempt to remove it")
        return False
    
    def OnEmptyServer(self, data, isStartup):
        """Handle empty server event - switch to default map/mode"""
        doMap = self._config.cfg["rtv"]["emptyServerMap"]["enabled"]
        doMode = self._config.cfg["rtm"]["emptyServerMode"]["enabled"]
        # cancel current vote if there is one
        if self._currentVote != None:
            print("last player dc'ed, killing current vote")
            self._currentVote = None
        if doMap and doMode:
            self._serverData.interface.MbMode(MBMODE_ID_MAP[self._config.cfg["rtm"]["emptyServerMode"]["mode"]], self._config.cfg["rtv"]["emptyServerMap"]["map"])
        elif doMap:
            self._serverData.interface.MapReload(self._config.cfg["rtv"]["emptyServerMap"]["map"])
        elif doMode:
            self._serverData.interface.MbMode(MBMODE_ID_MAP[self._config.cfg["rtm"]["emptyServerMode"]["mode"]])
        return False

    def OnClientChange(self, eventClient : client.Client, eventData : dict):
        """Handle client changes"""
        if self._config.cfg["kickProtectedNames"] == True:
            kickClientIfProtectedName(eventClient)


    def OnServerInit(self, data):
        """Handle server initialization (round start)"""
        self._roundTimer += 1
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        
        # Check if we should start an automatic vote
        if not self._currentVote and (votesInProgress == None or len(votesInProgress) == 0) and not self._rtvToSwitch and not self._rtmToSwitch:
            if self._config.cfg["rtv"]["roundLimit"]["enabled"] == True and self._roundTimer > self._config.cfg["rtv"]["roundLimit"]["rounds"]:
                self._StartRTVVote()
                self._roundTimer = 0
            elif self._config.cfg["rtm"]["roundLimit"]["enabled"] == True and self._roundTimer > self._config.cfg["rtm"]["roundLimit"]["rounds"]:
                self._StartRTMVote()
                self._roundTimer = 0
        
        # Process pending map/mode changes
        if self._rtvToSwitch != None:
            self._SwitchRTV(self._rtvToSwitch)
        elif self._rtmToSwitch != None:
            self._SwitchRTM(self._rtmToSwitch)
        return False

    def OnServerShutdown(self):
        """Handle server shutdown (not implemented)"""
        return False

    def OnClientKill(self, eventClient, eventVictim, eventWeaponStr):
        """Handle client kill event (not implemented)"""
        return False

    def OnPlayer(self, client, data):
        """Handle player event (not implemented)"""
        return False

    def OnExit(self, eventData):
        """Handle exit event (not implemented)"""
        return False
    
    def OnMapChange(self, mapName, oldMapName) -> bool:
        """Handle map change event"""
        Log.debug(f"Map change event received: {mapName}")
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        # Clean up vote tracking
        if votesInProgress != None and "RTV" in votesInProgress:
            votesInProgress.remove("RTV")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)
        # Update current map
        if mapName != self._mapName:
            self._mapName = mapName
        # Reset current vote
        self._currentVote = None
        return False

    def HandleForceRTV(self, playerName, smodId, adminIP, cmdArgs):
        """Handle smod !forcertv command - force start RTV vote"""
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        # Check if RTV can be forced
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            self.SvSay("Smod forced RTV vote")
            self._StartRTVVote()
        return True

    def HandleForceRTM(self, playerName, smodId, adminIP, cmdArgs):
        """Handle smod !forcertm command - force start RTM vote"""
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        # Check if RTV can be forced
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            self.SvSay("Smod forced RTM vote")
            self._StartRTMVote()
        return True

    def HandleRTVEnable(self, playerName, smodId, adminIP, cmdArgs):
        """Handle smod !rtvenable command - force reset the cooldown for RTV"""
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        # Check if RTV can be forced
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if self._config.cfg["rtv"]["enabled"] and self._rtvCooldown.IsSet():
                self.SvSay("SMOD reset the cooldown for RTV!")
                self._rtvCooldown.Finish()
            elif not self._config.cfg["rtv"]["enabled"]:
                self._serverData.interface.SmSay(self._messagePrefix + "RTV is not enabled.")
            elif not self._rtvCooldown.IsSet():
                self._serverData.interface.SmSay(self._messagePrefix + "RTV is not on cooldown.")
        return True

    def HandleRTMEnable(self, playerName, smodId, adminIP, cmdArgs):
        """Handle smod !rtmenable command - force reset the cooldown for RTM"""
        currentVote = self._currentVote
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        # Check if RTV can be forced
        if not currentVote and (votesInProgress == None or len(votesInProgress) == 0):
            if self._config.cfg["rtm"]["enabled"] and self._rtmCooldown.IsSet():
                self.SvSay("SMOD reset the cooldown for RTM!")
                self._rtmCooldown.Finish()
            elif not self._config.cfg["rtm"]["enabled"]:
                self._serverData.interface.SmSay(self._messagePrefix + "RTM is not enabled.")
            elif not self._rtmCooldown.IsSet():
                self._serverData.interface.SmSay(self._messagePrefix + "RTM is not on cooldown.")
        return True

    def HandleSmodCommand(self, playerName, smodId, adminIP, cmdArgs):
        """Route smod command to appropriate handler"""
        command = cmdArgs[0]
        if command.startswith("!"):
            command = command[len("!"):]
        for c in self._smodCommandList:
            if command in c:
                return self._smodCommandList[c][1](playerName, smodId, adminIP, cmdArgs)
        return False
    
    def Start(self) -> bool:
        """Initialize plugin with current players"""
        allClients = self._serverData.API.GetAllClients()
        for cl in allClients:
            newPlayer = RTVPlayer(cl)
            self._OnNewPlayer(newPlayer)
        return True

    def OnSmsay(self, senderName : str, smodID : int, senderIP : str, message : str):
        """Handle smod chat messages"""
        message = message.lower()
        messageParse = message.split()
        return self.HandleSmodCommand(senderName, smodID, senderIP, messageParse)

class RTVNomination(object):
    """Represents a player's map nomination"""
    def __init__(self, player, map):
        self._player : RTVPlayer = player
        self._map : Map = map

    def GetPlayer(self) -> RTVPlayer:
        """Get nominating player"""
        return self._player

    def GetMap(self) -> Map:
        """Get nominated map"""
        return self._map

# Plugin lifecycle functions below with detailed explanations

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    startTime = time()
    
    # Get current map
    serverMap = PluginInstance._serverData.mapName
    if serverMap == '': # godfinger hasn't initialized map yet
        serverMap = PluginInstance._serverData.interface.GetCvar("mapname")
    PluginInstance._mapName = serverMap
    
    # Initialize plugin
    if not PluginInstance.Start():
        return False
    
    # Kick protected names if enabled TODO this should probably be made its own plugin at some point
    if PluginInstance._config.cfg["kickProtectedNames"] == True:
        for i in PluginInstance._serverData.API.GetAllClients():
            kickClientIfProtectedName(i)
    
    # Report startup time
    loadTime = time() - startTime
    PluginInstance.Say(f"RTV started in {loadTime:.2f} seconds!")
    return True 

def kickClientIfProtectedName(client : client.Client):
    nameStripped = colors.StripColorCodes(client.GetName().lower())
    nameStripped = re.sub(r":|-|\.|,|;|=|\/|\\|\||`|~|\"|\'|[|]|(|)|_", "", nameStripped)
    if nameStripped in [x.lower() for x in PluginInstance._config.cfg["protectedNames"]]:
        PluginInstance._serverData.interface.ClientKick(client.GetId()) # indicate plugin start success

# Called each loop tick from the system
def OnLoop():
    PluginInstance._doLoop()

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    global PluginInstance
    del PluginInstance

# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports=None):
    global SERVER_DATA
    SERVER_DATA = serverData

    # Configure logging
    logMode = logging.INFO
    if serverData.args.debug:
        logMode = logging.DEBUG
    if serverData.args.logfile != "":
        logging.basicConfig(
            filename=serverData.args.logfile,
            level=logMode,
            format='%(asctime)s %(levelname)08s %(name)s %(message)s')
    else:
        logging.basicConfig(
            level=logMode,
            format='%(asctime)s %(levelname)08s %(name)s %(message)s')

    # Create plugin instance
    global PluginInstance
    PluginInstance = RTV(serverData)
    
    # Register API exports
    if exports != None:
        exports.Add("StartRTVVote", API_StartRTVVote)
    
    # Register commands with server
    newVal = []
    # Check for existing help command from another plugin before using this plugin's
    rCommands = PluginInstance._serverData.GetServerVar("registeredCommands")
    if rCommands != None and 'help' in [x for x, _ in rCommands]:
        del PluginInstance._commandList[teams.TEAM_GLOBAL][('help', "cmds")]

    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for i in cmd:
            if not i.isdecimal():
                newVal.append((i, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newVal)
    return True  # indicate plugin load success

def API_StartRTVVote(allowNoChange=True):
    """API function to start RTV vote externally"""
    Log.debug("Received external RTV vote request")
    global PluginInstance
    votesInProgress = PluginInstance._serverData.GetServerVar("votesInProgress")
    # Check if vote can be started
    if not PluginInstance._currentVote and (votesInProgress == None or len(votesInProgress) == 0):
        PluginInstance._StartRTVVote(allowNoChange=allowNoChange)
        return True
    return False

def OnEvent(event) -> bool:
    """Route Godfinger events to appropriate handlers"""
    global PluginInstance
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return PluginInstance.OnChatMessage( event.client, event.message, event.teamId )
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return PluginInstance.OnClientConnect( event.client)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return PluginInstance.OnClientChange( event.client, event.data )
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return PluginInstance.OnClientDisconnect( event.client, event.reason )
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return PluginInstance.OnServerInit(event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return PluginInstance.OnServerShutdown()
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return PluginInstance.OnClientKill(event.client, event.victim, event.weaponStr)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return PluginInstance.OnPlayer(event.client, event.data["text"] if "text" in event.data else "")
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return PluginInstance.OnExit(event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return PluginInstance.OnMapChange(event.mapName, event.oldMapName)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SERVER_EMPTY:
        return PluginInstance.OnEmptyServer(event.data, event.isStartup)    
    return False

# Helper function to get all map names from currently installed PK3 files located in MBII directory and base directory next to MBII
def GetAllMaps() -> list[Map]:
    """Scan PK3 files in MBII directories to discover available maps"""
    mbiiDir = os.path.abspath(DEFAULT_CFG.cfg["MBIIPath"])
    if not os.path.exists(mbiiDir):
        # try to find the MBII directory relatively
        Log.info(f"Directory {mbiiDir} does not exist. Attempting to resolve relatively...")
        searchDir = os.getcwd()
        while True:
            if os.path.exists(os.path.join(searchDir, "MBII")):
                mbiiDir = os.path.join(searchDir, "MBII")
                Log.info(f"SUCCESS! Found MBII directory at {mbiiDir}.")
                break
            else:
                oldDir = searchDir
                searchDir = os.path.dirname(searchDir)
                if oldDir == searchDir:
                    # we've hit the top
                    Log.error(f"FAILURE. No MBII directory found. Will try and go ahead with the path in the config but will probably crash.")
                    break
    mapList = []
    dirsToProcess = [mbiiDir, os.path.normpath(os.path.join(mbiiDir, "../base"))]; # base comes next so it wont override MBII dir contents if files match
    for sub_dir in dirsToProcess:
        for filename in os.listdir(sub_dir):
            if filename.endswith(".pk3"):
                with ZipFile(os.path.join(sub_dir, filename)) as file:
                    zipNameList = file.namelist()
                    for name in zipNameList:
                        # Process BSP files as map objects
                        if name.endswith(".bsp") and not name in [x.GetMapName() for x in mapList]:
                            path = name
                            name = name.lower().replace("maps/", "").replace(".bsp", "")
                            newMap = Map(name, path)
                            mapList.append(newMap)
    return mapList