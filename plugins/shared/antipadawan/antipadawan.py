
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
# Admin tracking is in-memory only (not persisted to disk - cleared on restart)

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

        # Track admin-applied marks and mutes (in-memory only, cleared on restart)
        # Format: { "player_ip": { "marktk": {...}, "mute": {...} } }
        # Each entry: { "expires": timestamp, "duration": minutes, "admin_name": str, "admin_id": str }
        self._admin_tracking = {}

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

    def OnClientChanged(self, client: client.Client, data: dict) -> bool:
        """Handle client info changes - apply penalties if name changed to blocked name"""
        try:
            # Check if plugin is enabled
            if not self.config.cfg["enabled"]:
                return False

            # Check if name was changed
            if "name" not in data:
                return False  # Name didn't change, ignore

            player_ip = client.GetIp()
            new_name = client.GetName()
            old_name = data["name"]

            # Check if NEW name is blocked
            if self._IsPadawanName(client):
                # Player changed TO a blocked name while in-game
                # Apply penalties and track them
                Log.info(f"Player changed name to blocked name '{new_name}' (IP: {player_ip}) - applying penalties")
                self._HandlePadawan(client)

            # If player changed FROM blocked name to allowed name while in-game:
            # DO NOT remove penalties here - they must disconnect and rejoin to clear penalties
            # This prevents the exploit where players use name changes to clear admin-applied marks
            elif player_ip in self._tracking:
                Log.info(f"Player '{old_name}' changed name to '{new_name}' - penalties remain until disconnect/rejoin")
                # Update tracking with new name
                self._tracking[player_ip]["lastSeenName"] = new_name
                self._SaveTracking()
        except Exception as e:
            Log.error(f"Error in OnClientChanged: {e}")
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

                    # Unmute if they were muted BY THE PLUGIN
                    if self._tracking[player_ip].get("muted", False):
                        # Check if there's an active admin mute - if so, don't clear
                        has_admin_mute = False
                        if player_ip in self._admin_tracking and "mute" in self._admin_tracking[player_ip]:
                            # Clean up expired admin mutes
                            if time.time() >= self._admin_tracking[player_ip]["mute"]["expires"]:
                                del self._admin_tracking[player_ip]["mute"]
                                if not self._admin_tracking[player_ip]:  # Empty dict
                                    del self._admin_tracking[player_ip]
                                Log.info(f"Admin mute for {player_ip} has expired")
                            else:
                                has_admin_mute = True
                                Log.warning(f"Player {player_name} has admin mute - NOT clearing mute (expires in {int((self._admin_tracking[player_ip]['mute']['expires'] - time.time()) / 60)} min)")

                        if not has_admin_mute:
                            # No admin mute or it expired - safe to clear
                            try:
                                self._serverData.interface.ClientUnmute(player_id)
                                Log.info(f"Unmuted {player_name} (ID: {player_id})")
                            except Exception as e:
                                Log.error(f"Failed to unmute player {player_id}: {e}")

                    # Unmark TK if they were marked BY THE PLUGIN
                    if self._tracking[player_ip].get("markedTK", False):
                        # Check if there's an active admin mark - if so, don't clear
                        has_admin_mark = False
                        if player_ip in self._admin_tracking and "marktk" in self._admin_tracking[player_ip]:
                            # Clean up expired admin marks
                            if time.time() >= self._admin_tracking[player_ip]["marktk"]["expires"]:
                                del self._admin_tracking[player_ip]["marktk"]
                                if not self._admin_tracking[player_ip]:  # Empty dict
                                    del self._admin_tracking[player_ip]
                                Log.info(f"Admin mark for {player_ip} has expired")
                            else:
                                has_admin_mark = True
                                Log.warning(f"Player {player_name} has admin mark - NOT clearing TK mark (expires in {int((self._admin_tracking[player_ip]['marktk']['expires'] - time.time()) / 60)} min)")

                        if not has_admin_mark:
                            # No admin mark or it expired - safe to clear
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

            # Remove special characters and digits for better matching
            # This handles cases like "padawan[1]" -> "padawan"
            name_clean = re.sub(r"[:\-.,;=/\\|`~\"'\[\]\(\)_\d]", "", name_stripped)

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

    def OnSmsay(self, playerName: str, smodID: int, adminIP: str, message: str) -> bool:
        """Handle admin commands from smsay"""
        # Only process if plugin is enabled
        if not self.config.cfg["enabled"]:
            return False

        try:
            # Only process !gf commands
            message_lower = message.lower()
            if message_lower.startswith("!gf"):
                parts = message_lower.split()
                command = parts[0]

                # !gfmarktk <playername> <duration>
                if command == "!gfmarktk" and len(parts) >= 3:
                    target_name = parts[1]
                    try:
                        duration = int(parts[2])
                    except ValueError:
                        return False

                    # Find player by name
                    all_clients = self._serverData.API.GetAllClients()
                    target_client = None
                    for cl in all_clients:
                        if target_name.lower() in cl.GetName().lower():
                            target_client = cl
                            break

                    if target_client:
                        target_ip = target_client.GetIp()
                        target_id = target_client.GetId()

                        # Mark the player
                        self._serverData.interface.MarkTK(target_id, duration)

                        # Track admin mark
                        if target_ip not in self._admin_tracking:
                            self._admin_tracking[target_ip] = {}
                        self._admin_tracking[target_ip]["marktk"] = {
                            "expires": time.time() + (duration * 60),
                            "duration": duration,
                            "admin_name": playerName,
                            "admin_ip": adminIP
                        }

                        self._serverData.interface.SvSay(self._messagePrefix + f"Admin marked {target_client.GetName()} for TK ({duration} min)")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) marked {target_client.GetName()} (IP: {target_ip}) for TK - tracked for {duration} min")
                        return False

                # !gfmute <playername> <duration>
                elif command == "!gfmute" and len(parts) >= 3:
                    target_name = parts[1]
                    try:
                        duration = int(parts[2])
                    except ValueError:
                        return False

                    # Find player by name
                    all_clients = self._serverData.API.GetAllClients()
                    target_client = None
                    for cl in all_clients:
                        if target_name.lower() in cl.GetName().lower():
                            target_client = cl
                            break

                    if target_client:
                        target_ip = target_client.GetIp()
                        target_id = target_client.GetId()

                        # Mute the player
                        self._serverData.interface.ClientMute(target_id, duration)

                        # Track admin mute
                        if target_ip not in self._admin_tracking:
                            self._admin_tracking[target_ip] = {}
                        self._admin_tracking[target_ip]["mute"] = {
                            "expires": time.time() + (duration * 60),
                            "duration": duration,
                            "admin_name": playerName,
                            "admin_ip": adminIP
                        }

                        self._serverData.interface.SvSay(self._messagePrefix + f"Admin muted {target_client.GetName()} ({duration} min)")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) muted {target_client.GetName()} (IP: {target_ip}) - tracked for {duration} min")
                        return False

                # !gfunmarktk <playername>
                elif command == "!gfunmarktk" and len(parts) >= 2:
                    target_name = parts[1]

                    # Find player by name
                    all_clients = self._serverData.API.GetAllClients()
                    target_client = None
                    for cl in all_clients:
                        if target_name.lower() in cl.GetName().lower():
                            target_client = cl
                            break

                    if target_client:
                        target_ip = target_client.GetIp()
                        target_id = target_client.GetId()

                        # Unmark the player
                        self._serverData.interface.UnmarkTK(target_id)

                        # Remove admin tracking for marktk
                        if target_ip in self._admin_tracking and "marktk" in self._admin_tracking[target_ip]:
                            del self._admin_tracking[target_ip]["marktk"]
                            if not self._admin_tracking[target_ip]:  # Empty dict
                                del self._admin_tracking[target_ip]

                        self._serverData.interface.SvSay(self._messagePrefix + f"Admin unmarked {target_client.GetName()}")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) unmarked {target_client.GetName()} (IP: {target_ip})")
                        return False

                # !gfunmute <playername>
                elif command == "!gfunmute" and len(parts) >= 2:
                    target_name = parts[1]

                    # Find player by name
                    all_clients = self._serverData.API.GetAllClients()
                    target_client = None
                    for cl in all_clients:
                        if target_name.lower() in cl.GetName().lower():
                            target_client = cl
                            break

                    if target_client:
                        target_ip = target_client.GetIp()
                        target_id = target_client.GetId()

                        # Unmute the player
                        self._serverData.interface.ClientUnmute(target_id)

                        # Remove admin tracking for mute
                        if target_ip in self._admin_tracking and "mute" in self._admin_tracking[target_ip]:
                            del self._admin_tracking[target_ip]["mute"]
                            if not self._admin_tracking[target_ip]:  # Empty dict
                                del self._admin_tracking[target_ip]

                        self._serverData.interface.SvSay(self._messagePrefix + f"Admin unmuted {target_client.GetName()}")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) unmuted {target_client.GetName()} (IP: {target_ip})")
                        return False

                # !padawanips - Show all tracked IPs to admin
                elif command == "!padawanips":
                    # Find the admin client to send them private messages
                    admin_client = None
                    for cl in self._serverData.API.GetAllClients():
                        if cl.GetIp() == adminIP:
                            admin_client = cl
                            break

                    if not admin_client:
                        Log.warning(f"Could not find admin client for IP {adminIP}")
                        return False

                    admin_id = admin_client.GetId()

                    # Load current tracking data
                    tracking_data = self._LoadTracking()

                    if not tracking_data:
                        self._serverData.interface.SvTell(admin_id, self._messagePrefix + "^2No tracked IPs found.")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) requested tracked IPs - none found")
                        return False

                    # Send header
                    self._serverData.interface.SvTell(admin_id, self._messagePrefix + f"^5Tracked IPs ({len(tracking_data)} total):")

                    # Send each tracked IP with details
                    for ip, data in tracking_data.items():
                        last_name = data.get("lastSeenName", "Unknown")
                        marked_tk = "^1YES" if data.get("markedTK", False) else "^2NO"
                        muted = "^1YES" if data.get("muted", False) else "^2NO"

                        msg = f"^7IP: ^5{ip} ^7| Name: ^3{last_name} ^7| MarkedTK: {marked_tk} ^7| Muted: {muted}"
                        self._serverData.interface.SvTell(admin_id, msg)

                    Log.info(f"Admin {playerName} (SMOD ID: {smodID}) requested tracked IPs - sent {len(tracking_data)} entries")
                    return False

                # !kickpadawans - Kick all players with blocked names
                elif command == "!kickpadawans":
                    # Get all connected clients
                    all_clients = self._serverData.API.GetAllClients()
                    kicked_players = []

                    # Check each client for blocked name
                    for cl in all_clients:
                        if self._IsPadawanName(cl):
                            player_name = cl.GetName()
                            player_id = cl.GetId()

                            # Kick the player
                            try:
                                self._serverData.interface.ClientKick(player_id)
                                kicked_players.append(player_name)
                                Log.info(f"Admin {playerName} kicked {player_name} (ID: {player_id}) via !kickpadawans")
                            except Exception as e:
                                Log.error(f"Failed to kick player {player_id}: {e}")

                    # Report results
                    if kicked_players:
                        kicked_count = len(kicked_players)
                        strict_mode = "strict" if self.config.cfg.get("strictMatch", True) else "loose"
                        self._serverData.interface.SvSay(self._messagePrefix + f"^1Admin kicked {kicked_count} player(s) with blocked names (^5{strict_mode} mode^1)")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) kicked {kicked_count} players: {', '.join(kicked_players)}")
                    else:
                        self._serverData.interface.SvSay(self._messagePrefix + "^2No players with blocked names found.")
                        Log.info(f"Admin {playerName} (SMOD ID: {smodID}) used !kickpadawans - no players to kick")

                    return False

        except Exception as e:
            Log.error(f"Error in OnSmsay: {e}")
            return False

        return False  # Don't capture event



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
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        if event.isStartup:
            return False  # Ignore startup messages
        else:
            return PluginInstance.OnClientChanged(event.client, event.data)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        if event.isStartup:
            return False  # Ignore startup messages
        else:
            return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)
    return False

if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system. Please run one of the start scripts in the start directory to use it. Make sure that this python module's path is included in godfingerCfg!")
    input("Press Enter to close this message.")
    exit()
