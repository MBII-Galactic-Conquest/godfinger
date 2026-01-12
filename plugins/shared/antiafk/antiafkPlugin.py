import godfingerEvent
import lib.shared.client as client
import lib.shared.teams as teams
import lib.shared.colors as colors
from lib.shared.serverdata import ServerData
from lib.shared.player import Player
import logging
import json
import os

Log = logging.getLogger(__name__)

# Default configuration
DEFAULT_CONFIG = {
    "enabled": True,
    "maxSpectatorRounds": 5,
    "warningRounds": [3, 4],  # Rounds at which to send warnings
    "kickMessage": "^1was kicked for being AFK in spectator too long",
    "warningMessage": "^3Warning: Join a team or you will be kicked in {rounds} round(s)!",
    "messagePrefix": "^9[Anti-AFK]^7 ",
    "exemptJAGuids": [],  # List of ja_guids that are exempt from AFK kicks (dont use this)
    "resetOnMapChange": True,  # Reset AFK counters when map changes
    "exemptSmodUsers": True,  # Exempt players logged into SMOD from AFK kicks
    "minimumPlayers": 0  # Minimum number of players before AFK enforcement begins (0 = always enforce)
}

class AFKPlayer(Player):
    """Tracks AFK status for a player"""
    def __init__(self, player_client: client.Client):
        super().__init__(player_client)
        self._spectator_rounds = 0
        self._last_team = player_client.GetTeamId()
        self._is_smod_logged_in = False  # Track SMOD login status
    
    def GetSpectatorRounds(self) -> int:
        return self._spectator_rounds
    
    def IncrementSpectatorRounds(self):
        self._spectator_rounds += 1
    
    def ResetSpectatorRounds(self):
        self._spectator_rounds = 0
    
    def UpdateTeam(self, team_id: int):
        self._last_team = team_id
    
    def GetLastTeam(self) -> int:
        return self._last_team
    
    def SetSmodLoggedIn(self, logged_in: bool):
        """Set SMOD login status"""
        self._is_smod_logged_in = logged_in
    
    def IsSmodLoggedIn(self) -> bool:
        """Check if player is logged into SMOD"""
        return self._is_smod_logged_in

class AntiAFKPlugin:
    """Plugin to kick players who remain in spectator for too many rounds"""
    
    def __init__(self, server_data: ServerData):
        self._serverData = server_data
        self._players : dict[int, AFKPlayer] = {}  # Dict[int, AFKPlayer]
        self._config = self._load_config()
        self._messagePrefix = self._config["messagePrefix"]
        self._smod_ip_to_client = {}  # Map SMOD IP to client for login tracking
        
        Log.info("Anti-AFK Plugin initialized")
    
    def _load_config(self) -> dict:
        """Load configuration from JSON file or create default"""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "antiafk_config.json"
        )
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    Log.info(f"Loaded Anti-AFK config from {config_path}")
                    return config
            except Exception as e:
                Log.error(f"Failed to load config: {e}. Using defaults.")
                return DEFAULT_CONFIG
        else:
            # Create default config file
            try:
                with open(config_path, 'w') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
                    Log.info(f"Created default Anti-AFK config at {config_path}")
            except Exception as e:
                Log.error(f"Failed to create default config: {e}")
            return DEFAULT_CONFIG
    
    def _is_exempt(self, player_client: client.Client) -> bool:
        """Check if player is exempt from AFK kicks"""
        ja_guid = player_client._jaguid
        player_id = player_client.GetId()
        
        # Check ja_guid exemption
        if ja_guid in self._config["exemptJAGuids"]:
            return True
        
        # Check SMOD exemption
        if self._config.get("exemptSmodUsers", True):
            if player_id in self._players:
                afk_player = self._players[player_id]
                if afk_player.IsSmodLoggedIn():
                    Log.debug(f"Player {player_client.GetName()} (ID: {player_id}) exempt - logged into SMOD")
                    return True
        
        return False
    
    def _should_enforce_afk(self) -> bool:
        """Check if AFK enforcement should be active based on minimum player count"""
        if self._config.get("minimumPlayers", 0) <= 0:
            return True  # Always enforce if no minimum set
        
        total_players = len(self._serverData.API.GetAllClients())
        return total_players >= self._config["minimumPlayers"]
    
    def _check_and_warn_player(self, afk_player: AFKPlayer):
        """Check if player needs warning or kick"""
        if not self._config["enabled"]:
            return
        
        # Check if minimum player threshold is met
        total_players = self._serverData.API.GetClientCount()
        min_players = self._config.get("minimumPlayers", 0)
        
        if min_players > 0 and total_players < min_players:
            Log.debug(
                f"AFK enforcement disabled - player count ({total_players}) "
                f"below minimum threshold ({min_players})"
            )
            return
        
        player_client = afk_player.GetClient()
        
        # Skip if exempt
        if self._is_exempt(player_client):
            return
        
        rounds = afk_player.GetSpectatorRounds()
        max_rounds = self._config["maxSpectatorRounds"]
        
        # Check if player should be kicked
        if rounds >= max_rounds:
            self._kick_player(player_client)
            return
        
        # Check if player should receive warning
        if rounds in self._config["warningRounds"]:
            rounds_left = max_rounds - rounds
            warning_msg = self._config["warningMessage"].format(rounds=rounds_left)
            self._send_warning(player_client, warning_msg)
    
    def _kick_player(self, player_client: client.Client):
        """Kick player for being AFK"""
        player_id = player_client.GetId()
        player_name = player_client.GetName()
        
        Log.info(f"Kicking player {player_name} (ID: {player_id}) for AFK in spectator")
        
        # Send kick message to server
        self.SvSay(f"{player_name}^7 {self._config['kickMessage']}")
        
        # Kick the player
        self._serverData.interface.ClientKick(player_id)
    
    def _send_warning(self, player_client: client.Client, message: str):
        """Send warning message to player"""
        player_id = player_client.GetId()
        player_name = player_client.GetName()
        
        Log.debug(f"Sending AFK warning to {player_name} (ID: {player_id})")
        self.SvTell(player_id, message)
    
    def OnSmodLogin(self, data: dict) -> bool:
        """Handle SMOD login event"""
        if not self._config.get("exemptSmodUsers", True):
            return False
        
        smod_ip = data.get('admin_ip')
        smod_name = data.get('smod_name')
        
        if not smod_ip:
            Log.warning("SMOD login event missing IP address")
            return False
        
        # Find the client with matching IP
        all_clients = self._serverData.API.GetAllClients()
        for cl in all_clients:
            client_ip = cl.GetIp().split(':')[0]  # Strip port
            if client_ip == smod_ip:
                player_id = cl.GetId()
                if player_id in self._players:
                    afk_player = self._players[player_id]
                    afk_player.SetSmodLoggedIn(True)
                    Log.info(f"Player {cl.GetName()} (ID: {player_id}) logged into SMOD - now exempt from AFK kicks")
                    self.SvTell(player_id, "You are now exempt from AFK kicks (SMOD login)")
                    # Reset their AFK counter since they're now exempt
                    if afk_player.GetSpectatorRounds() > 0:
                        Log.debug(f"Resetting AFK counter for SMOD user {cl.GetName()}")
                        afk_player.ResetSpectatorRounds()
                break
        
        return False
    
    def OnServerInit(self, data: dict, is_startup: bool) -> bool:
        """Handle round start - increment spectator counters"""
        if not self._config["enabled"]:
            return False
        
        # Skip enforcement if not enough players
        if not self._should_enforce_afk():
            return False
        
        Log.debug("Round started - checking spectator players")
        
        for player_id, afk_player in list(self._players.items()):
            player_client = afk_player.GetClient()
            current_team = player_client.GetTeamId()
            
            # Only track players in spectator
            if current_team == teams.TEAM_SPEC:
                afk_player.IncrementSpectatorRounds()
                Log.debug(
                    f"Player {player_client.GetName()} (ID: {player_id}) "
                    f"spectator rounds: {afk_player.GetSpectatorRounds()}"
                )
                self._check_and_warn_player(afk_player)
        
        return False
    
    def OnClientConnect(self, event_client: client.Client) -> bool:
        """Handle new client connection"""
        player_id = event_client.GetId()
        
        if player_id not in self._players:
            afk_player = AFKPlayer(event_client)
            self._players[player_id] = afk_player
            Log.debug(f"Added new player {event_client.GetName()} (ID: {player_id}) to AFK tracking")
        
        return False
    
    def OnClientDisconnect(self, event_client: client.Client, reason: int) -> bool:
        """Handle client disconnection"""
        player_id = event_client.GetId()
        
        if player_id in self._players:
            del self._players[player_id]
            Log.debug(f"Removed player {event_client.GetName()} (ID: {player_id}) from AFK tracking")
        
        return False
    
    def OnClientChange(self, event_client: client.Client, changed_data: dict) -> bool:
        """Handle client team changes"""
        player_id = event_client.GetId()
        
        if player_id not in self._players:
            Log.warning(f"Player {player_id} changed but not in tracking")
            return False
        
        afk_player = self._players[player_id]
        
        # Check if team changed
        if "team" in changed_data:
            old_team = changed_data["team"]
            new_team = event_client.GetTeamId()
            
            Log.debug(
                f"Player {event_client.GetName()} (ID: {player_id}) "
                f"changed team from {old_team} to {new_team}"
            )
            
            # Reset counter if player joins a non-spectator team
            if new_team != teams.TEAM_SPEC and old_team == teams.TEAM_SPEC:
                if afk_player.GetSpectatorRounds() > 0:
                    Log.info(
                        f"Player {event_client.GetName()} (ID: {player_id}) "
                        f"joined a team - resetting AFK counter"
                    )
                    afk_player.ResetSpectatorRounds()
            
            afk_player.UpdateTeam(new_team)
        
        return False
    
    def OnPlayerSpawn(self, event_client: client.Client, vars: dict) -> bool:
        """Handle player spawn event"""
        player_id = event_client.GetId()
        
        if player_id not in self._players:
            Log.warning(f"Player {player_id} spawned but not in tracking")
            return False
        
        afk_player = self._players[player_id]
        current_team = event_client.GetTeamId()
        
        # Reset counter if player spawns on a non-spectator team
        if current_team != teams.TEAM_SPEC:
            if afk_player.GetSpectatorRounds() > 0:
                Log.debug(
                    f"Player {event_client.GetName()} (ID: {player_id}) "
                    f"spawned on team - resetting AFK counter"
                )
                afk_player.ResetSpectatorRounds()
        
        return False
    
    def OnMapChange(self, mapName: str, oldMapName: str) -> bool:
        """Handle map change event"""
        if not self._config.get("resetOnMapChange", True):
            return False
        
        Log.info(f"Map changed from {oldMapName} to {mapName} - resetting AFK counters")
        
        # Reset all players' spectator rounds
        for player_id, afk_player in self._players.items():
            if afk_player.GetSpectatorRounds() > 0:
                player_name = afk_player.GetClient().GetName()
                Log.debug(
                    f"Resetting AFK counter for {player_name} (ID: {player_id}) "
                    f"from {afk_player.GetSpectatorRounds()} rounds"
                )
                afk_player.ResetSpectatorRounds()
        
        return False
    
    def Start(self) -> bool:
        """Initialize plugin with current players"""
        all_clients = self._serverData.API.GetAllClients()
        
        for cl in all_clients:
            afk_player = AFKPlayer(cl)
            self._players[cl.GetId()] = afk_player
            Log.debug(f"Added existing player {cl.GetName()} (ID: {cl.GetId()}) to AFK tracking")
        
        return True
    
    def SvTell(self, player_id: int, message: str):
        """Send message to specific player"""
        self._serverData.interface.SvTell(player_id, f"{self._messagePrefix}{message}")
    
    def SvSay(self, message: str):
        """Send message to all players"""
        self._serverData.interface.SvSay(f"{self._messagePrefix}{message}")


# Global plugin instance
PluginInstance = None
SERVER_DATA = None


def OnInitialize(serverData: ServerData, exports=None):
    """Initialize the plugin"""
    global SERVER_DATA, PluginInstance
    SERVER_DATA = serverData
    
    # Configure logging
    log_mode = logging.INFO
    if serverData.args.debug:
        log_mode = logging.DEBUG
    
    if serverData.args.logfile != "":
        logging.basicConfig(
            filename=serverData.args.logfile,
            level=log_mode,
            format='%(asctime)s %(levelname)08s %(name)s %(message)s'
        )
    else:
        logging.basicConfig(
            level=log_mode,
            format='%(asctime)s %(levelname)08s %(name)s %(message)s'
        )
    
    # Create plugin instance
    PluginInstance = AntiAFKPlugin(serverData)
    
    Log.info("Anti-AFK Plugin loaded successfully")
    return True


def OnLoop():
    """Called each loop tick from the system"""
    pass


def OnStart():
    """Start the plugin"""
    global PluginInstance
    
    if not PluginInstance.Start():
        Log.error("Failed to start Anti-AFK Plugin")
        return False
    return True


def OnFinish():
    """Called when plugin is being shut down"""
    pass


def OnEvent(event) -> bool:
    """Route events to appropriate handlers"""
    global PluginInstance
    
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return PluginInstance.OnClientConnect(event.client)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return PluginInstance.OnClientChange(event.client, event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return PluginInstance.OnClientDisconnect(event.client, event.reason)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return PluginInstance.OnServerInit(event.data, event.isStartup)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return PluginInstance.OnMapChange(event.mapName, event.oldMapName)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return PluginInstance.OnPlayerSpawn(event.client, event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMOD_LOGIN:
        return PluginInstance.OnSmodLogin({"smod_name" : event.playerName, "smod_id" : event.smodID, "admin_ip" : event.adminIP})
    
    return False