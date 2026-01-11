
import logging
import godfingerEvent
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import lib.shared.client as client
import lib.shared.colors as colors
import re
import os
import json
import time

SERVER_DATA = None

CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "antipadawanCfg.json")
TRACKING_FILE_PATH = os.path.join(os.path.dirname(__file__), "antipadawan_tracking.json")

CONFIG_FALLBACK = \
"""{
    "enabled": true,
    "action": 0,
    "strictMatch": true,
    "silentMode": false,
    "messagePrefix": "^1[Anti-Padawan]^7: ",
    "privateMessage": "^1Please change your username to play on this server.^7 Your username is blocked.",
    "marktkDuration": 60,
    "muteDuration": 60,
    "detectedWords": ["padawan"]
}
"""
global AntiPadawanConfig
AntiPadawanConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

# DISCLAIMER : DO NOT LOCK ANY OF THESE FUNCTIONS, IF YOU WANT MAKE INTERNAL LOOPS FOR PLUGINS - MAKE OWN THREADS AND MANAGE THEM, LET THESE FUNCTIONS GO.

Log = logging.getLogger(__name__)


PluginInstance = None

class AntiPadawan():
    def __init__(self, serverData: serverdata.ServerData):
        self._status = 0
        self._serverData = serverData
        self.config = AntiPadawanConfig
        self._messagePrefix = self.config.cfg["messagePrefix"]

        # Validate configuration
        if self.config.cfg["action"] not in [0, 1, 2, 3]:
            Log.error("Invalid action value %d, defaulting to 0", self.config.cfg["action"])
            self.config.cfg["action"] = 0

        # Load tracking data
        self._tracking = self._LoadTracking()

    def Start(self) -> bool:
        """Check all existing players on startup"""
        if not self.config.cfg["enabled"]:
            return True

        allClients = self._serverData.API.GetAllClients()
        for cl in allClients:
            if self._IsPadawanName(cl):
                Log.info(f"Detected padawan name on startup: {cl.GetName()} (ID: {cl.GetId()})")
                self._HandlePadawan(cl)

        if self._status == 0:
            return True
        else:
            return False

    def Finish(self):
        pass

    def OnClientConnect(self, client: client.Client, data: dict) -> bool:
        """Handle client connection - detect padawan names"""
        try:
            # Check if plugin is enabled
            if not self.config.cfg["enabled"]:
                return False

            # Check if player has padawan in name
            if self._IsPadawanName(client):
                Log.info(f"Detected padawan name: {client.GetName()} (ID: {client.GetId()})")
                self._HandlePadawan(client)
        except Exception as e:
            Log.error(f"Error in OnClientConnect detection logic: {e}")
            return False

        return False  # Don't capture event

    def OnClientBegin(self, client: client.Client, data: dict) -> bool:
        """Handle client begin - remove penalties if name changed (called when client is ready)"""
        try:
            # Check if plugin is enabled
            if not self.config.cfg["enabled"]:
                return False

            player_ip = client.GetIp()
            player_id = client.GetId()
            player_name = client.GetName()

            # Check if this IP was previously penalized
            if player_ip in self._tracking:
                # Check if their current name is allowed
                if not self._IsPadawanName(client):
                    # Name is now allowed - remove penalties
                    Log.info(f"Player {player_name} (IP: {player_ip}) changed name from blocked name - removing penalties")

                    # Unmute if they were muted
                    if self._tracking[player_ip].get("muted", False):
                        try:
                            self._serverData.interface.ClientUnmute(player_id)
                            Log.info(f"Unmuted {player_name} (ID: {player_id})")
                        except Exception as e:
                            Log.error(f"Failed to unmute player {player_id}: {e}")

                    # Unmark TK if they were marked
                    if self._tracking[player_ip].get("markedTK", False):
                        try:
                            self._serverData.interface.UnmarkTK(player_id)
                            Log.info(f"Cleared TK mark for {player_name} (ID: {player_id})")
                        except Exception as e:
                            Log.error(f"Failed to clear TK mark for player {player_id}: {e}")

                    # Send message letting them know they're cleared (unless in silent mode)
                    if not self.config.cfg.get("silentMode", False):
                        try:
                            self._serverData.interface.SvTell(player_id,
                                self._messagePrefix + "^2Thank you for changing your name! Penalties removed.")
                        except Exception as e:
                            Log.error(f"Failed to send clear message to player {player_id}: {e}")

                    # Remove from tracking
                    try:
                        del self._tracking[player_ip]
                        self._SaveTracking()
                    except Exception as e:
                        Log.error(f"Failed to remove tracking for IP {player_ip}: {e}")
                else:
                    # Still has blocked name - check if penalties need to be applied
                    if self._tracking[player_ip].get("pendingAction0", False):
                        # Apply action 0 penalty now that player is fully ready
                        Log.info(f"Applying action 0 penalty to {player_name} (ID: {player_id}) - waiting 2 seconds for client to be fully ready")

                        # Wait a second to ensure client is fully in the game
                        time.sleep(1)

                        marktk_duration = self.config.cfg["marktkDuration"]

                        # Execute MarkTK
                        try:
                            self._serverData.interface.MarkTK(player_id, marktk_duration)
                            Log.info(f"Marked TK for {player_name} (ID: {player_id}) for {marktk_duration} min")
                        except Exception as e:
                            Log.error(f"Failed to mark TK for player {player_id}: {e}")

                        # Remove pendingAction0 flag
                        self._tracking[player_ip]["pendingAction0"] = False
                        self._SaveTracking()

                    elif self._tracking[player_ip].get("pendingAction3", False):
                        # Apply action 3 penalties now that player is fully ready
                        Log.info(f"Applying action 3 penalties to {player_name} (ID: {player_id}) - waiting 2 seconds for client to be fully ready")

                        # Wait a second to ensure client is fully in the game
                        time.sleep(1)

                        marktk_duration = self.config.cfg["marktkDuration"]
                        mute_duration = self.config.cfg["muteDuration"]

                        # Execute MarkTK first
                        try:
                            self._serverData.interface.MarkTK(player_id, marktk_duration)
                            Log.info(f"Marked TK for {player_name} (ID: {player_id}) for {marktk_duration} min")
                        except Exception as e:
                            Log.error(f"Failed to mark TK for player {player_id}: {e}")

                        # Small delay between commands
                        time.sleep(0.2)

                        # Then mute
                        try:
                            self._serverData.interface.ClientMute(player_id, mute_duration)
                            Log.info(f"Muted {player_name} (ID: {player_id}) for {mute_duration} min")
                        except Exception as e:
                            Log.error(f"Failed to mute player {player_id}: {e}")

                        # Remove pendingAction3 flag
                        self._tracking[player_ip]["pendingAction3"] = False
                        self._SaveTracking()
                    else:
                        # Penalties already applied, just log
                        Log.info(f"Player {player_name} (IP: {player_ip}) still has blocked name - penalties remain")
        except Exception as e:
            Log.error(f"Error in OnClientBegin penalty logic: {e}")
            return False

        return False  # Don't capture event

    def _IsPadawanName(self, client: client.Client) -> bool:
        """Check if player name contains any blocked words (case-insensitive, color-stripped)"""
        try:
            name = client.GetName()
            name_stripped = colors.StripColorCodes(name).lower()

            # Remove special characters for better matching
            name_clean = re.sub(r":|-|\.|,|;|=|\/|\\|\||`|~|\"|'|[|]|(|)|_", "", name_stripped)

            # Support both legacy "detectedWord" (string) and new "detectedWords" (list)
            detected_words = []
            if "detectedWords" in self.config.cfg:
                detected_words = [word.lower() for word in self.config.cfg["detectedWords"]]
            elif "detectedWord" in self.config.cfg:
                detected_words = [self.config.cfg["detectedWord"].lower()]

            # Get strictMatch setting (default to False for backwards compatibility)
            strict_match = self.config.cfg.get("strictMatch", False)

            # Check if any blocked word is in the name
            for word in detected_words:
                if strict_match:
                    # Strict mode: name must be exactly the blocked word (after cleaning)
                    if name_clean == word:
                        Log.debug(f"Detected blocked word '{word}' (strict match) in player name: {name}")
                        return True
                else:
                    # Loose mode: blocked word can be part of the name
                    if word in name_clean:
                        Log.debug(f"Detected blocked word '{word}' (loose match) in player name: {name}")
                        return True
            return False
        except Exception as e:
            Log.error(f"Error checking player name: {e}")
            return False

    def _SendPrivateMessage(self, client: client.Client):
        """Send private message to player asking them to change name"""
        # Skip if silent mode is enabled
        if self.config.cfg.get("silentMode", False):
            return

        player_id = client.GetId()
        message = self.config.cfg["privateMessage"]

        try:
            self._serverData.interface.SvTell(player_id, message)
            Log.debug(f"Sent private message to {client.GetName()} (ID: {player_id})")
        except Exception as e:
            Log.error(f"Error sending private message to player {player_id}: {e}")

    def _HandlePadawan(self, client: client.Client):
        """Execute configured action on detected padawan"""
        action = self.config.cfg["action"]
        player_id = client.GetId()
        player_name = client.GetName()
        player_ip = client.GetIp()

        # Always send private message
        self._SendPrivateMessage(client)

        if action == 0:
            # MarkTK immediately, allow play
            # Track this IP - command will be executed in OnClientBegin when player is fully ready
            self._tracking[player_ip] = {
                "markedTK": True,
                "muted": False,
                "timestamp": time.time(),
                "lastSeenName": player_name,
                "pendingAction0": True  # Flag to indicate action 0 command needs to be executed
            }
            self._SaveTracking()
            Log.info(f"Detected padawan {player_name} (ID: {player_id}) - will apply action 0 penalty when ready")

        elif action == 1:
            # Kick player (no tracking needed - they're gone)
            self._serverData.interface.ClientKick(player_id)
            Log.info(f"Kicked {player_name} (ID: {player_id}) for padawan name")

        elif action == 2:
            # Ban IP then kick (no tracking needed - they're banned)
            self._serverData.interface.ClientBan(player_ip)
            self._serverData.interface.ClientKick(player_id)
            Log.info(f"Banned and kicked {player_name} (ID: {player_id}, IP: {player_ip})")

        elif action == 3:
            # MarkTK and mute, allow play
            # Track this IP - commands will be executed in OnClientBegin when player is fully ready
            self._tracking[player_ip] = {
                "markedTK": True,
                "muted": True,
                "timestamp": time.time(),
                "lastSeenName": player_name,
                "pendingAction3": True  # Flag to indicate action 3 commands need to be executed
            }
            self._SaveTracking()
            Log.info(f"Detected padawan {player_name} (ID: {player_id}) - will apply action 3 penalties when ready")

    def _LoadTracking(self) -> dict:
        """Load tracking data from JSON file"""
        try:
            if os.path.exists(TRACKING_FILE_PATH):
                with open(TRACKING_FILE_PATH, "r") as f:
                    tracking = json.load(f)
                Log.debug(f"Loaded tracking data for {len(tracking)} IPs")
                return tracking
            else:
                Log.debug("No tracking file found, starting with empty tracking")
                return {}
        except Exception as e:
            Log.error(f"Failed to load tracking data: {e}")
            return {}

    def _SaveTracking(self):
        """Save tracking data to JSON file"""
        try:
            with open(TRACKING_FILE_PATH, "w") as f:
                json.dump(self._tracking, f, indent=4)
            Log.debug(f"Saved tracking data for {len(self._tracking)} IPs")
        except Exception as e:
            Log.error(f"Failed to save tracking data: {e}")


# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData: serverdata.ServerData, exports=None) -> bool:
    global SERVER_DATA
    SERVER_DATA = serverData  # keep it stored
    global PluginInstance
    PluginInstance = AntiPadawan(serverData)
    if exports != None:
        pass

    if PluginInstance._status < 0:
        Log.error("Anti-Padawan plugin failed to initialize")
        return False

    return True  # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    return PluginInstance.Start()

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    global PluginInstance
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        if event.isStartup:
            return False  # Ignore startup messages
        else:
            return PluginInstance.OnClientConnect(event.client, event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        if event.isStartup:
            return False  # Ignore startup messages
        else:
            return PluginInstance.OnClientBegin(event.client, event.data)
    return False

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()
