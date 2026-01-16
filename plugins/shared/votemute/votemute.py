"""
VoteMute Plugin - Player-initiated vote to mute

Allows players to vote to mute another player on the server.
- !votemute <player> - Start a vote to mute a player
- !1 - Vote yes
- !2 - Vote no

SMOD Commands:
    !overridevotemute 1 - Force vote to pass (admin override)
    !overridevotemute 2 - Force vote to fail (admin override)
    !togglevotemute - Enable/disable votemute

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

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "votemuteCfg.json")

CONFIG_FALLBACK = """{
    "enabled": true,
    "majorityThreshold": 0.75,
    "minimumParticipation": 0.5,
    "voteDuration": 60,
    "muteDuration": 15,
    "voteCooldown": 120,
    "silentMode": false,
    "messagePrefix": "^5[VoteMute]^7: "
}"""

VotemuteConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

PluginInstance = None


class VotemutePlugin:
    def __init__(self, serverData: serverdata.ServerData):
        self._serverData = serverData
        self.config = VotemuteConfig
        self._messagePrefix = self.config.cfg.get("messagePrefix", "^5[VoteMute]^7: ")

        # Vote state
        self._activeVote = None
        self._voteCooldown = Timeout()

        # Chat command registration
        self._commandList = {
            teams.TEAM_GLOBAL: {
                tuple(["votemute", "vm"]): ("!votemute <player> - Start vote to mute player", self.HandleVotemute),
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
            tuple(["overridevotemute", "ovm"]): ("!overridevotemute <1|2> - Override active votemute (1=pass, 2=fail)", self.HandleOverrideVote),
            tuple(["togglevotemute", "tvm"]): ("!togglevotemute - Enable/disable votemute", self.HandleToggleVote),
        }

    def SvSay(self, message: str):
        """Send message to all players"""
        if not self.config.cfg.get("silentMode", False):
            self._serverData.interface.SvSay(self._messagePrefix + message)

    def SvTell(self, player_id: int, message: str):
        """Send private message to a player"""
        if not self.config.cfg.get("silentMode", False):
            self._serverData.interface.SvTell(player_id, self._messagePrefix + message)

    def _CanStartVote(self) -> tuple:
        """Check if a vote can be started. Returns (can_start, reason)"""
        if not self._runtimeEnabled:
            return (False, "VoteMute is currently disabled")

        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress and len(votesInProgress) > 0:
            return (False, f"Another vote is in progress: {', '.join(votesInProgress)}")

        if self._voteCooldown.IsSet():
            return (False, f"VoteMute is on cooldown for {self._voteCooldown.LeftDHMS()}")

        return (True, None)

    def _RegisterVote(self):
        """Register this vote in votesInProgress to prevent conflicts"""
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress is None:
            self._serverData.SetServerVar("votesInProgress", ["VoteMute"])
        else:
            votesInProgress.append("VoteMute")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)

    def _UnregisterVote(self):
        """Unregister this vote from votesInProgress"""
        votesInProgress = self._serverData.GetServerVar("votesInProgress")
        if votesInProgress and "VoteMute" in votesInProgress:
            votesInProgress.remove("VoteMute")
            self._serverData.SetServerVar("votesInProgress", votesInProgress)

    def _FindPlayerByName(self, name_query: str) -> client.Client:
        """Find a player by name (partial match, case-insensitive)"""
        name_lower = name_query.lower()
        for cl in self._serverData.API.GetAllClients():
            client_name = colors.StripColorCodes(cl.GetName()).lower()
            if name_lower == client_name or name_lower in client_name:
                return cl
        return None

    def _StartVote(self, initiator: client.Client, target: client.Client):
        """Start a votemute against target"""
        self._activeVote = {
            "target_id": target.GetId(),
            "target_name": target.GetName(),
            "initiator_id": initiator.GetId(),
            "votes_yes": [initiator.GetId()],
            "votes_no": [],
            "start_time": time()
        }
        self._RegisterVote()

        target_name_clean = colors.StripColorCodes(target.GetName())
        initiator_name = colors.StripColorCodes(initiator.GetName())
        total_players = len(self._serverData.API.GetAllClients())
        eligible_voters = total_players - 1  # Target cannot vote on their own votemute
        votes_needed = ceil(eligible_voters * self.config.cfg.get("majorityThreshold", 0.75))

        self.SvSay(f"{initiator_name}^7 started a vote to ^5MUTE^7 {target_name_clean}^7. Type ^2!1^7 for YES, ^1!2^7 for NO. (1/{votes_needed} needed)")
        Log.info(f"VoteMute started by {initiator_name} against {target_name_clean}")

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

        total_players = len(self._serverData.API.GetAllClients())
        eligible_voters = total_players - 1  # Target cannot vote
        yes_count = len(self._activeVote["votes_yes"])
        no_count = len(self._activeVote["votes_no"])
        total_voters = yes_count + no_count
        votes_needed = ceil(eligible_voters * self.config.cfg.get("majorityThreshold", 0.75))
        minimum_participation = self.config.cfg.get("minimumParticipation", 0.5)
        minimum_voters_needed = ceil(eligible_voters * minimum_participation)
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

    def _ApplyPunishment(self):
        """Apply mute to the target player"""
        if self._activeVote is None:
            return

        target_id = self._activeVote["target_id"]
        target_name = self._activeVote["target_name"]
        mute_duration = self.config.cfg.get("muteDuration", 15)

        try:
            self._serverData.interface.ClientMute(target_id, mute_duration)
            Log.info(f"VoteMute passed: {target_name} muted for {mute_duration} minutes")
        except Exception as e:
            Log.error(f"Error applying mute: {e}")

    def _EndVote(self, apply_cooldown: bool = True):
        """End the current vote and clean up"""
        self._UnregisterVote()
        self._activeVote = None

        if apply_cooldown:
            cooldown = self.config.cfg.get("voteCooldown", 120)
            self._voteCooldown.Set(cooldown)

    def HandleVotemute(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Handle !votemute command"""
        if len(cmdArgs) < 2:
            self.SvTell(eventClient.GetId(), "Usage: !votemute <player>")
            return True

        can_start, reason = self._CanStartVote()
        if not can_start:
            self.SvTell(eventClient.GetId(), reason)
            return True

        # Find target player
        target_name = " ".join(cmdArgs[1:])
        target = self._FindPlayerByName(target_name)

        if target is None:
            self.SvTell(eventClient.GetId(), f"Player '{target_name}' not found")
            return True

        # Cannot vote against self
        if target.GetId() == eventClient.GetId():
            self.SvTell(eventClient.GetId(), "You cannot start a votemute against yourself")
            return True

        self._StartVote(eventClient, target)
        return True

    def HandleVoteYes(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Handle !1 command (vote yes)"""
        if self._activeVote is None:
            return False  # Don't capture if no vote active

        # Target cannot vote on their own votemute
        if eventClient.GetId() == self._activeVote["target_id"]:
            self.SvTell(eventClient.GetId(), "You cannot vote on your own votemute")
            return True

        self._HandleVote(eventClient.GetId(), True)

        total_players = len(self._serverData.API.GetAllClients())
        eligible_voters = total_players - 1  # Target cannot vote
        yes_count = len(self._activeVote["votes_yes"])
        votes_needed = ceil(eligible_voters * self.config.cfg.get("majorityThreshold", 0.75))

        # Announce progress
        target_name = colors.StripColorCodes(self._activeVote["target_name"])
        self.SvSay(f"Vote to mute {target_name}^7: ^2{yes_count}^7/{votes_needed} YES votes")

        return True

    def HandleVoteNo(self, eventClient: client.Client, teamId: int, cmdArgs: list) -> bool:
        """Handle !2 command (vote no)"""
        if self._activeVote is None:
            return False  # Don't capture if no vote active

        # Target cannot vote on their own votemute
        if eventClient.GetId() == self._activeVote["target_id"]:
            self.SvTell(eventClient.GetId(), "You cannot vote on your own votemute")
            return True

        self._HandleVote(eventClient.GetId(), False)
        return True

    def HandleOverrideVote(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """SMOD command to override active vote"""
        if self._activeVote is None:
            self._serverData.interface.SmSay(self._messagePrefix + "No active votemute to override")
            return True

        if len(cmdArgs) < 2 or cmdArgs[1] not in ["1", "2"]:
            self._serverData.interface.SmSay(self._messagePrefix + "Usage: !overridevote <1|2>")
            return True

        target_name = colors.StripColorCodes(self._activeVote["target_name"])

        if cmdArgs[1] == "1":
            # Force pass
            self._ApplyPunishment()
            self.SvSay(f"Vote to mute {target_name}^7 ^2PASSED^7 (admin override)")
            Log.info(f"VoteMute override by SMOD {smodID}: PASSED for {target_name}")
        else:
            # Force fail
            self.SvSay(f"Vote to mute {target_name}^7 ^1FAILED^7 (admin override)")
            Log.info(f"VoteMute override by SMOD {smodID}: FAILED for {target_name}")

        self._EndVote()
        return True

    def HandleToggleVote(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """SMOD command to toggle votemute on/off"""
        self._runtimeEnabled = not self._runtimeEnabled
        status = "^2ENABLED" if self._runtimeEnabled else "^1DISABLED"
        self._serverData.interface.SmSay(self._messagePrefix + f"VoteMute is now {status}")
        Log.info(f"VoteMute toggled to {self._runtimeEnabled} by SMOD {smodID}")

        # Cancel active vote if disabling
        if not self._runtimeEnabled and self._activeVote:
            target_name = colors.StripColorCodes(self._activeVote["target_name"])
            self.SvSay(f"Vote to mute {target_name}^7 cancelled - VoteMute disabled by admin")
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

    def OnClientDisconnect(self, eventClient: client.Client, reason: int) -> bool:
        """Handle client disconnect - cancel vote if target leaves"""
        if self._activeVote is None:
            return False

        if eventClient.GetId() == self._activeVote["target_id"]:
            target_name = colors.StripColorCodes(self._activeVote["target_name"])
            self.SvSay(f"Vote to mute {target_name}^7 cancelled - player disconnected")
            self._EndVote(apply_cooldown=False)

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
        if result == "pass":
            target_name = colors.StripColorCodes(self._activeVote["target_name"])
            yes_count = len(self._activeVote["votes_yes"])
            self.SvSay(f"Vote to mute {target_name}^7 ^2PASSED^7 with {yes_count} votes!")
            self._ApplyPunishment()
            self._EndVote()
        elif result == "fail":
            target_name = colors.StripColorCodes(self._activeVote["target_name"])
            yes_count = len(self._activeVote["votes_yes"])
            total_players = len(self._serverData.API.GetAllClients())
            eligible_voters = total_players - 1  # Target cannot vote
            votes_needed = ceil(eligible_voters * self.config.cfg.get("majorityThreshold", 0.75))
            self.SvSay(f"Vote to mute {target_name}^7 ^1FAILED^7 ({yes_count}/{votes_needed})")
            self._EndVote()
        elif result == "insufficient":
            target_name = colors.StripColorCodes(self._activeVote["target_name"])
            yes_count = len(self._activeVote["votes_yes"])
            no_count = len(self._activeVote["votes_no"])
            total_voters = yes_count + no_count
            total_players = len(self._serverData.API.GetAllClients())
            eligible_voters = total_players - 1  # Target cannot vote
            minimum_participation = self.config.cfg.get("minimumParticipation", 0.5)
            minimum_voters_needed = ceil(eligible_voters * minimum_participation)
            self.SvSay(f"Vote to mute {target_name}^7 ^1FAILED^7 - not enough participation ({total_voters}/{minimum_voters_needed} needed)")
            self._EndVote()

    def Start(self) -> bool:
        """Plugin startup"""
        if not self.config.cfg.get("enabled", True):
            Log.info("VoteMute plugin is disabled in configuration")
            return True

        Log.info("VoteMute plugin started")
        Log.info(f"Majority threshold: {self.config.cfg.get('majorityThreshold', 0.51) * 100}%")
        Log.info(f"Minimum participation: {self.config.cfg.get('minimumParticipation', 0.5) * 100}%")
        Log.info(f"Vote duration: {self.config.cfg.get('voteDuration', 60)} seconds")
        Log.info(f"Mute duration: {self.config.cfg.get('muteDuration', 15)} minutes")
        return True

    def Finish(self):
        """Plugin shutdown"""
        if self._activeVote:
            self._UnregisterVote()
        Log.info("VoteMute plugin stopped")


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
    PluginInstance = VotemutePlugin(serverData)

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
    return PluginInstance.Start()


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

        elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
            return PluginInstance.OnClientDisconnect(event.client, event.reason)

    except Exception as e:
        Log.error(f"Error in OnEvent: {e}")

    return False


if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system.")
    print("Please run one of the start scripts in the start directory to use it.")
    input("Press Enter to close this message.")
    exit()
