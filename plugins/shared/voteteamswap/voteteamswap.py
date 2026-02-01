"""
VoteTeamSwap Plugin - Player-initiated vote to toggle g_teamSwap

Allows players to vote to enable or disable team swapping on the server.
- !voteteamswap - Start a vote to toggle g_teamSwap
- !1 - Vote yes
- !2 - Vote no

SMOD Commands:
    !overridevoteteamswap 1 - Force vote to pass (admin override)
    !overridevoteteamswap 2 - Force vote to fail (admin override)
    !togglevoteteamswap - Enable/disable voteteamswap feature

Non-voters count as NO votes.
Majority threshold is configurable.
"""

import os
import logging
from time import time
from math import ceil

import godfingerEvent
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import lib.shared.client as client
import lib.shared.colors as colors
import lib.shared.teams as teams
from lib.shared.timeout import Timeout

SERVER_DATA = None
Log = logging.getLogger(__name__)

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "voteteamswapCfg.json")

CONFIG_FALLBACK = """{
    "enabled": true,
    "majorityThreshold": 0.75,
    "minimumParticipation": 0.5,
    "voteDuration": 60,
    "voteCooldown": 120,
    "silentMode": false,
    "messagePrefix": "^3[VoteTeamSwap]^7: "
}"""

VoteteamswapConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

PluginInstance = None


class VoteteamswapPlugin:
    def __init__(self, serverData: serverdata.ServerData):
        self._serverData = serverData
        self.config = VoteteamswapConfig
        self._messagePrefix = self.config.cfg.get("messagePrefix", "^3[VoteTeamSwap]^7: ")

        # Vote state
        self._activeVote = None
        self._voteCooldown = Timeout()

        # Chat command registration
        self._commandList = {
            teams.TEAM_GLOBAL: {
                tuple(["voteteamswap", "vts"]): ("!voteteamswap - Start vote to toggle team swap", self.HandleVoteTeamSwap),
                tuple(["1"]): ("", self.HandleVoteYes),
                tuple(["2"]): ("", self.HandleVoteNo),
            },
            teams.TEAM_EVIL: {
                tuple(["1"]): ("", self.HandleVoteYes),
                tuple(["2"]): ("", self.HandleVoteNo),
            },
            teams.TEAM_GOOD: {
                tuple(["1"]): ("", self.HandleVoteYes),
                tuple(["2"]): ("", self.HandleVoteNo),
            },
            teams.TEAM_SPEC: {
                tuple(["1"]): ("", self.HandleVoteYes),
                tuple(["2"]): ("", self.HandleVoteNo),
            }
        }

        # Runtime enabled state (can be toggled by SMOD)
        self._runtimeEnabled = self.config.cfg.get("enabled", True)

        # SMOD command registration
        self._smodCommandList = {
            tuple(["overridevoteteamswap", "ovts"]): ("!overridevoteteamswap <1|2> - Override active vote (1=pass, 2=fail)", self.HandleOverrideVote),
            tuple(["togglevoteteamswap", "tvts"]): ("!togglevoteteamswap - Enable/disable voteteamswap", self.HandleToggleVote),
        }

    def SvSay(self, message: str):
        """Send message to all players"""
        if not self.config.cfg.get("silentMode", False):
            self._serverData.interface.SvSay(self._messagePrefix + message)

    def SvTell(self, player_id: int, message: str):
        """Send private message to a player"""
        if not self.config.cfg.get("silentMode", False):
            self._serverData.interface.SvTell(player_id, self._messagePrefix + message)

    def _GetCurrentTeamSwapState(self) -> str:
        """Get current g_teamSwap value from server"""
        try:
            result = self._serverData.interface.GetCvar("g_teamSwap")
            if result:
                # Clean up the result - might contain extra formatting
                result = result.strip()
                if result in ["0", "1"]:
                    return result
                # Try to extract just the value if it contains quotes or other chars
                for char in result:
                    if char in ["0", "1"]:
                        return char
        except Exception as e:
            Log.error(f"Error getting g_teamSwap: {e}")
        return "0"  # Default to off if unknown

    def _IsLocalhost(self, client_ip: str) -> bool:
        """Check if IP is localhost"""
        ip = client_ip.split(':')[0] if ':' in client_ip else client_ip
        return ip == "127.0.0.1" or ip.startswith("127.")

    def _GetRealPlayerCount(self) -> int:
        """Get count of real players (excluding localhost/fake clients)"""
        count = 0
        for cl in self._serverData.API.GetAllClients():
            if not self._IsLocalhost(cl.GetIp()):
                count += 1
        return count

    def _CanStartVote(self) -> tuple:
        """Check if a vote can be started. Returns (can_start, reason)"""
        if not self._runtimeEnabled:
            return (False, "VoteTeamSwap is currently disabled")

        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress and len(votesInProgress) > 0:
            return (False, f"Another vote is in progress: {', '.join(votesInProgress)}")

        if self._voteCooldown.IsSet():
            return (False, f"VoteTeamSwap is on cooldown for {self._voteCooldown.LeftDHMS()}")

        return (True, None)

    def _RegisterVote(self):
        """Register this vote in votesInProgress to prevent conflicts"""
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress is None:
            self._serverData.SetServerVar("votesInProgress", ["VoteTeamSwap"])
        else:
            votesInProgress.append("VoteTeamSwap")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)

    def _UnregisterVote(self):
        """Unregister this vote from votesInProgress"""
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress and "VoteTeamSwap" in votesInProgress:
            votesInProgress.remove("VoteTeamSwap")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)

    def _StartVote(self, initiator: client.Client, target_value: str):
        """Start a vote to change g_teamSwap"""
        total_players = self._GetRealPlayerCount()
        votes_needed = ceil(total_players * self.config.cfg.get("majorityThreshold", 0.75))
        minimum_participation = self.config.cfg.get("minimumParticipation", 0.5)
        minimum_voters_needed = ceil(total_players * minimum_participation)

        self._activeVote = {
            "initiator_id": initiator.GetId(),
            "initiator_name": initiator.GetName(),
            "votes_yes": [initiator.GetId()],
            "votes_no": [],
            "start_time": time(),
            "target_value": target_value,
            "votes_needed": votes_needed,
            "minimum_voters_needed": minimum_voters_needed,
            "total_players_at_start": total_players
        }
        self._RegisterVote()

        initiator_name = colors.StripColorCodes(initiator.GetName())
        action = "^2ENABLE" if target_value == "1" else "^1DISABLE"

        self.SvSay(f"{initiator_name}^7 started a vote to {action}^7 team swap. Type ^2!1^7 for YES, ^1!2^7 for NO. (1/{votes_needed} needed)")
        Log.info(f"VoteTeamSwap started by {initiator_name} to set g_teamSwap={target_value}")

    def _HandleVote(self, player_id: int, vote_yes: bool):
        """Record a player's vote"""
        if self._activeVote is None:
            return

        # Remove from opposite list if already voted
        if vote_yes:
            if player_id in self._activeVote["votes_no"]:
                self._activeVote["votes_no"].remove(player_id)
            if player_id not in self._activeVote["votes_yes"]:
                self._activeVote["votes_yes"].append(player_id)
        else:
            if player_id in self._activeVote["votes_yes"]:
                self._activeVote["votes_yes"].remove(player_id)
            if player_id not in self._activeVote["votes_no"]:
                self._activeVote["votes_no"].append(player_id)

    def _CheckVoteResult(self) -> str:
        """Check if vote has concluded. Returns 'pass', 'fail', 'insufficient', or 'pending'"""
        if self._activeVote is None:
            return "pending"

        yes_count = len(self._activeVote["votes_yes"])
        no_count = len(self._activeVote["votes_no"])
        total_voters = yes_count + no_count
        votes_needed = self._activeVote["votes_needed"]
        minimum_voters_needed = self._activeVote["minimum_voters_needed"]
        vote_duration = self.config.cfg.get("voteDuration", 60)
        time_expired = time() - self._activeVote["start_time"] >= vote_duration

        # Check if enough players voted (participation threshold)
        if time_expired and total_voters < minimum_voters_needed:
            return "insufficient"

        if yes_count >= votes_needed:
            return "pass"
        elif time_expired:
            return "fail"
        return "pending"

    def _ApplyTeamSwap(self):
        """Set g_teamSwap to the voted value"""
        if self._activeVote is None:
            return

        target_value = self._activeVote["target_value"]

        try:
            self._serverData.interface.SetCvar("g_teamSwap", target_value)
            action = "enabled" if target_value == "1" else "disabled"
            Log.info(f"VoteTeamSwap passed: g_teamSwap {action}")
        except Exception as e:
            Log.error(f"Error setting g_teamSwap: {e}")

    def _EndVote(self, apply_cooldown: bool = True):
        """End the current vote and clean up"""
        self._UnregisterVote()
        self._activeVote = None

        if apply_cooldown:
            cooldown = self.config.cfg.get("voteCooldown", 120)
            self._voteCooldown.Set(cooldown)

    def HandleVoteTeamSwap(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Handle !voteteamswap command"""
        can_start, reason = self._CanStartVote()
        if not can_start:
            self.SvTell(eventClient.GetId(), reason)
            return True

        # Determine what we're voting for (toggle current state)
        current = self._GetCurrentTeamSwapState()
        target_value = "0" if current == "1" else "1"

        self._StartVote(eventClient, target_value)
        return True

    def HandleVoteYes(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Handle !1 command (vote yes)"""
        if self._activeVote is None:
            return False  # Don't capture if no vote active

        self._HandleVote(eventClient.GetId(), True)

        yes_count = len(self._activeVote["votes_yes"])
        votes_needed = self._activeVote["votes_needed"]

        # Announce progress
        action = "enable" if self._activeVote["target_value"] == "1" else "disable"
        self.SvSay(f"Vote to {action} team swap: ^2{yes_count}^7/{votes_needed} YES votes")

        return True

    def HandleVoteNo(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Handle !2 command (vote no)"""
        if self._activeVote is None:
            return False  # Don't capture if no vote active

        self._HandleVote(eventClient.GetId(), False)
        return True

    def HandleOverrideVote(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """SMOD command to override active vote"""
        if self._activeVote is None:
            self._serverData.interface.SmSay(self._messagePrefix + "No active vote to override")
            return True

        if len(cmdArgs) < 2 or cmdArgs[1] not in ["1", "2"]:
            self._serverData.interface.SmSay(self._messagePrefix + "Usage: !overridevoteteamswap <1|2>")
            return True

        action = "enable" if self._activeVote["target_value"] == "1" else "disable"

        if cmdArgs[1] == "1":
            # Force pass
            self._ApplyTeamSwap()
            self.SvSay(f"Vote to {action} team swap ^2PASSED^7 (admin override)")
            Log.info(f"VoteTeamSwap override by SMOD {smodID}: PASSED")
        else:
            # Force fail
            self.SvSay(f"Vote to {action} team swap ^1FAILED^7 (admin override)")
            Log.info(f"VoteTeamSwap override by SMOD {smodID}: FAILED")

        self._EndVote()
        return True

    def HandleToggleVote(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """SMOD command to toggle voteteamswap on/off"""
        self._runtimeEnabled = not self._runtimeEnabled
        status = "^2ENABLED" if self._runtimeEnabled else "^1DISABLED"
        self._serverData.interface.SmSay(self._messagePrefix + f"VoteTeamSwap is now {status}")
        Log.info(f"VoteTeamSwap toggled to {self._runtimeEnabled} by SMOD {smodID}")

        # Cancel active vote if disabling
        if not self._runtimeEnabled and self._activeVote:
            action = "enable" if self._activeVote["target_value"] == "1" else "disable"
            self.SvSay(f"Vote to {action} team swap cancelled - VoteTeamSwap disabled by admin")
            self._EndVote(apply_cooldown=False)

        return True

    def HandleSmodCommand(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """Dispatch SMOD commands"""
        command = cmdArgs[0]
        if command.startswith("!"):
            command = command[1:]

        for c in self._smodCommandList:
            if command in c:
                return self._smodCommandList[c][1](playerName, smodID, adminIP, cmdArgs)
        return False

    def HandleChatCommand(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Route chat commands to handlers"""
        command = cmdArgs[0].lower()
        if command.startswith("!"):
            command = command[1:]

        if teamId in self._commandList:
            for c in self._commandList[teamId]:
                if command in c:
                    return self._commandList[teamId][c][1](eventClient, teamId, cmdArgs)
        return False

    def OnChatMessage(self, eventClient: client.Client, message: str, teamId: int) -> bool:
        """Handle chat messages"""
        if eventClient is None:
            return False

        if message.startswith("!"):
            message = message[1:]
            if len(message) > 0:
                cmdArgs = message.split()
                return self.HandleChatCommand(eventClient, teamId, cmdArgs)
        return False

    def OnSmsay(self, playerName: str, smodID: int, adminIP: str, message: str) -> bool:
        """Handle SMOD smsay commands"""
        if not self.config.cfg.get("enabled", True):
            return False

        message_lower = message.lower()
        messageParse = message_lower.split()
        return self.HandleSmodCommand(playerName, smodID, adminIP, messageParse)

    def DoLoop(self):
        """Main loop - check vote status"""
        if self._activeVote is None:
            return

        result = self._CheckVoteResult()
        action = "enable" if self._activeVote["target_value"] == "1" else "disable"

        if result == "pass":
            yes_count = len(self._activeVote["votes_yes"])
            self.SvSay(f"Vote to {action} team swap ^2PASSED^7 with {yes_count} votes!")
            self._ApplyTeamSwap()
            self._EndVote()
        elif result == "fail":
            yes_count = len(self._activeVote["votes_yes"])
            votes_needed = self._activeVote["votes_needed"]
            self.SvSay(f"Vote to {action} team swap ^1FAILED^7 ({yes_count}/{votes_needed})")
            self._EndVote()
        elif result == "insufficient":
            yes_count = len(self._activeVote["votes_yes"])
            no_count = len(self._activeVote["votes_no"])
            total_voters = yes_count + no_count
            minimum_voters_needed = self._activeVote["minimum_voters_needed"]
            self.SvSay(f"Vote to {action} team swap ^1FAILED^7 - not enough participation ({total_voters}/{minimum_voters_needed} needed)")
            self._EndVote()

    def Start(self) -> bool:
        """Plugin startup"""
        if not self.config.cfg.get("enabled", True):
            Log.info("VoteTeamSwap plugin is disabled in configuration")
            return True

        Log.info("VoteTeamSwap plugin started")
        Log.info(f"Majority threshold: {self.config.cfg.get('majorityThreshold', 0.75) * 100}%")
        Log.info(f"Minimum participation: {self.config.cfg.get('minimumParticipation', 0.5) * 100}%")
        Log.info(f"Vote duration: {self.config.cfg.get('voteDuration', 60)} seconds")
        return True

    def Finish(self):
        """Plugin shutdown"""
        if self._activeVote:
            self._UnregisterVote()
        Log.info("VoteTeamSwap plugin stopped")


# Module-level functions required by Godfinger

def OnInitialize(serverData: serverdata.ServerData, exports=None) -> bool:
    """Called once when plugin loads"""
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

    global SERVER_DATA
    SERVER_DATA = serverData

    global PluginInstance
    PluginInstance = VoteteamswapPlugin(serverData)

    # Register SMOD commands (for !help display)
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredSmodCommands")
    if rCommands is not None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._smodCommandList:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._smodCommandList[cmd][0]))
    SERVER_DATA.SetServerVar("registeredSmodCommands", newVal)

    # Register chat commands (for !help display)
    newCommands = []
    rChatCommands = SERVER_DATA.GetServerVar("registeredCommands")
    if rChatCommands is not None:
        newCommands.extend(rChatCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for alias in cmd:
            if not alias.isdecimal():
                newCommands.append((alias, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newCommands)

    return True


def OnStart() -> bool:
    """Called after plugin initialization"""
    startTime = time()
    result = PluginInstance.Start()
    if result:
        loadTime = time() - startTime
        PluginInstance.SvSay(f"VoteTeamSwap started in {loadTime:.2f} seconds!")
    return result


def OnLoop():
    """Called on each server loop tick"""
    PluginInstance.DoLoop()


def OnFinish():
    """Called before plugin unload"""
    PluginInstance.Finish()


def OnEvent(event) -> bool:
    """Called for every event"""
    global PluginInstance

    try:
        if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
            return PluginInstance.OnChatMessage(event.client, event.message, event.teamId)

        elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
            return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)

    except Exception as e:
        Log.error(f"Error in OnEvent: {e}")

    return False


if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system.")
    print("Please run one of the start scripts in the start directory to use it.")
    input("Press Enter to close this message.")
    exit()
