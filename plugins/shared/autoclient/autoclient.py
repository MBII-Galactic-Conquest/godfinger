"""
AutoClient Plugin - Automatic fake client spawner for server population

Spawns fake game clients to make the server appear populated.
Fake clients are automatically removed as real players join.

Windows-only plugin - requires mbiided.x86.exe to be running.

SMOD Commands:
    !toggleautoclient - Enable/disable the plugin
    !autoclientstatus - Show current fake/real client counts
    !spawnfake <count> - Manually spawn N fake clients
    !killfakes - Kill all fake clients immediately
"""

import os
import logging
import subprocess
import platform
import random
import string
from time import time

import godfingerEvent
import lib.shared.serverdata as serverdata
import lib.shared.config as config
import lib.shared.client as client
import lib.shared.colors as colors
import lib.shared.teams as teams

Log = logging.getLogger(__name__)

# Check if running on Windows
IS_WINDOWS = platform.system() == 'Windows'

# Default configuration
CONFIG_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "autoclientCfg.json")
CONFIG_FALLBACK = """{
    "enabled": true,
    "maxFakeClients": 8,
    "clientExecutablePath": "C:/Path/To/mbii.x86.exe",
    "serverIP": "127.0.0.1",
    "serverPort": "29070",
    "launchDelay": 15,
    "nameList": ["Trooper", "Soldier", "Recruit", "Stormtrooper", "Rebel", "Cadet", "Scout", "Apprentice", "Padawan", "Initiate", "Cultist", "Rosh", "Kyle Katarn", "Tavion", "Alora", "Luke Skywalker", "Jerec", "Desann", "Master", "Guardian"],
    "randomNamePrefix": "",
    "useRandomNames": true,
    "messagePrefix": "^6[AutoClient]^7: ",
    "serverProcessName": "mbiided.x86.exe"
}"""

AutoClientConfig = config.Config.fromJSON(CONFIG_DEFAULT_PATH, CONFIG_FALLBACK)

SERVER_DATA = None
PluginInstance = None


class FakeClient:
    """Represents a spawned fake client process"""

    def __init__(self, process, name, spawn_time):
        self.process = process
        self.name = name
        self.spawn_time = spawn_time
        self.pid = process.pid
        self.client_id = None  # Set when client connects to server
        self.connected = False  # True once we've matched this to an in-game client

    def is_alive(self):
        """Check if the process is still running"""
        return self.process.poll() is None

    def terminate(self):
        """Terminate the process using PowerShell for reliable kill"""
        try:
            # Use PowerShell Stop-Process with -Id for a forceful kill by PID
            # This is more reliable than taskkill for detached processes
            result = subprocess.run(
                ["powershell", "-Command", f"Stop-Process -Id {self.pid} -Force -ErrorAction SilentlyContinue"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5
            )
            Log.debug(f"PowerShell terminate PID {self.pid}: returncode={result.returncode}")
            return True
        except subprocess.TimeoutExpired:
            Log.warning(f"Timeout terminating client {self.name} (PID: {self.pid})")
            return False
        except Exception as e:
            Log.error(f"Failed to terminate client {self.name}: {e}")
            # Fallback to taskkill
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(self.pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            except:
                pass
            return False


class AutoClientPlugin:
    """Plugin to spawn and manage fake game clients"""

    def __init__(self, serverData: serverdata.ServerData):
        self._serverData = serverData

        # Load config
        self.config = AutoClientConfig

        self._messagePrefix = self.config.cfg.get("messagePrefix", "^6[AutoClient]^7: ")
        self._runtimeEnabled = self.config.cfg.get("enabled", True)

        # Client tracking
        self._fakeClients = {}  # pid -> FakeClient
        self._nameIndex = 0
        self._lastSpawnTime = 0

        # SMOD command registration
        self._smodCommandList = {
            tuple(["toggleautoclient", "tac"]): ("!toggleautoclient - Enable/disable AutoClient", self.HandleToggle),
            tuple(["autoclientstatus", "acs"]): ("!autoclientstatus - Show client status", self.HandleStatus),
            tuple(["spawnfake"]): ("!spawnfake <count> - Spawn fake clients", self.HandleSpawnFake),
            tuple(["killfakes"]): ("!killfakes - Kill all fake clients", self.HandleKillFakes),
        }

        Log.info("AutoClient Plugin initialized")

    def _IsWindows(self) -> bool:
        """Check if running on Windows"""
        return IS_WINDOWS

    def _IsServerRunning(self) -> bool:
        """Check if the dedicated server process is running"""
        if not IS_WINDOWS:
            return False

        try:
            # Use tasklist to check for the process
            process_name = self.config.cfg.get("serverProcessName", "mbiided.x86.exe")
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return process_name.lower() in result.stdout.lower()
        except Exception as e:
            Log.error(f"Error checking server process: {e}")
            return False

    def _IsLocalhost(self, client_ip: str) -> bool:
        """Check if IP is localhost (fake client)"""
        ip = client_ip.split(':')[0] if ':' in client_ip else client_ip
        return ip == "127.0.0.1" or ip.startswith("127.")

    def _GetRealPlayerCount(self) -> int:
        """Count players that are NOT localhost (real players)"""
        count = 0
        for cl in self._serverData.API.GetAllClients():
            if not self._IsLocalhost(cl.GetIp()):
                count += 1
        return count

    def _GetFakePlayerCount(self) -> int:
        """Count players that ARE localhost (fake clients)"""
        count = 0
        for cl in self._serverData.API.GetAllClients():
            if self._IsLocalhost(cl.GetIp()):
                count += 1
        return count

    def _GetNextName(self) -> str:
        """Get next name from list or generate random"""
        name_list = self.config.cfg.get("nameList", [])

        if self._nameIndex < len(name_list):
            name = name_list[self._nameIndex]
            self._nameIndex += 1
            return name

        # Reset index if we've used all names
        if self._nameIndex >= len(name_list) and len(name_list) > 0:
            self._nameIndex = 0

        # Generate random name
        if self.config.cfg.get("useRandomNames", True):
            prefix = self.config.cfg.get("randomNamePrefix", "Guest_")
            suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            return f"{prefix}{suffix}"

        # Fall back to first name in list
        if name_list:
            return name_list[0]

        return "Player"

    def _CanSpawnNow(self) -> bool:
        """Check if enough time has passed since last spawn"""
        delay = self.config.cfg.get("launchDelay", 5)
        return (time() - self._lastSpawnTime) >= delay

    def _SpawnFakeClient(self) -> bool:
        """Spawn a new fake client process"""
        if not self._IsWindows():
            Log.warning("Cannot spawn clients: Not running on Windows")
            return False

        if not self._IsServerRunning():
            Log.warning("Cannot spawn clients: Server process not running")
            return False

        exe_path = self.config.cfg.get("clientExecutablePath", "")
        if not exe_path or not os.path.isfile(exe_path):
            Log.error(f"Client executable not found: {exe_path}")
            return False

        server_ip = self.config.cfg.get("serverIP", "127.0.0.1")
        server_port = self.config.cfg.get("serverPort", "29070")
        name = self._GetNextName()

        cmd = [
            exe_path,
            "+set", "fs_game", "MBII",
            "+set", "s_volume", "0",
            "+set", "s_musicvolume", "0",
            "+set", "s_doppler", "0",
            "+set", "s_initsound", "0",
            "+connect", f"{server_ip}:{server_port}",
            "+name", name
        ]

        try:
            # Use DETACHED_PROCESS to run independently and set low priority
            # SW_HIDE via startupinfo to minimize window visibility
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

            # DETACHED_PROCESS + BELOW_NORMAL_PRIORITY_CLASS to reduce impact
            creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW | 0x00004000  # BELOW_NORMAL_PRIORITY_CLASS

            process = subprocess.Popen(
                cmd,
                creationflags=creation_flags,
                startupinfo=startupinfo,
                cwd=os.path.dirname(exe_path) if os.path.dirname(exe_path) else None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )

            fake_client = FakeClient(process, name, time())
            self._fakeClients[process.pid] = fake_client
            self._lastSpawnTime = time()

            Log.info(f"Spawned fake client: {name} (PID: {process.pid})")
            return True

        except Exception as e:
            Log.error(f"Failed to spawn fake client: {e}")
            return False

    def _KickClientByName(self, name: str):
        """Kick a client from the server by name"""
        # Find the client by name and kick them
        for cl in self._serverData.API.GetAllClients():
            if cl.GetName() == name or name in cl.GetName():
                client_id = cl.GetId()
                self._serverData.interface.ClientKick(client_id)
                Log.debug(f"Kicked client {name} (ID: {client_id})")
                return True
        return False

    def _GetLocalhostClients(self) -> list:
        """Get all localhost clients currently in the server"""
        localhost_clients = []
        for cl in self._serverData.API.GetAllClients():
            if self._IsLocalhost(cl.GetIp()):
                localhost_clients.append(cl)
        return localhost_clients

    def _KickOneMatchedFakeClient(self) -> bool:
        """Find and remove one fake client that has a confirmed PID <-> client_id match"""
        for pid, fake in list(self._fakeClients.items()):
            if fake.connected and fake.client_id is not None:
                Log.info(f"Removing matched fake client: {fake.name} (ID: {fake.client_id}, PID: {pid})")
                self._serverData.interface.ClientKick(fake.client_id)
                fake.terminate()
                del self._fakeClients[pid]
                return True

        Log.debug("No matched fake clients available to remove")
        return False

    def _RemoveOldestFakeClient(self) -> bool:
        """Remove the oldest fake client"""
        if not self._fakeClients:
            return False

        # Find oldest by spawn time
        oldest_pid = min(self._fakeClients.keys(),
                         key=lambda p: self._fakeClients[p].spawn_time)

        fake = self._fakeClients.pop(oldest_pid)

        Log.info(f"Removing fake client: {fake.name} (PID: {oldest_pid})")

        # Terminate process FIRST - this is more reliable
        # The kick may fail if client is in limbo state
        terminated = fake.terminate()

        # Also try to kick from server as backup
        self._KickClientByName(fake.name)

        if terminated:
            Log.info(f"Successfully terminated fake client: {fake.name} (PID: {oldest_pid})")
        else:
            Log.warning(f"May have failed to terminate fake client: {fake.name} (PID: {oldest_pid})")

        return True

    def _RemoveAllFakeClients(self):
        """Terminate all fake clients - both matched and unmatched"""
        count = len(self._fakeClients)
        for pid, fake in list(self._fakeClients.items()):
            # If matched, kick by client_id (reliable)
            if fake.connected and fake.client_id is not None:
                self._serverData.interface.ClientKick(fake.client_id)
                Log.info(f"Kicked matched fake client: {fake.name} (ID: {fake.client_id})")

            # Always terminate the process by PID
            fake.terminate()
            Log.info(f"Terminated fake client process: {fake.name} (PID: {pid})")

        self._fakeClients.clear()
        return count

    def _CheckClientHealth(self):
        """Remove dead clients from tracking"""
        dead_pids = [pid for pid, fake in self._fakeClients.items() if not fake.is_alive()]
        for pid in dead_pids:
            fake = self._fakeClients.pop(pid)
            Log.debug(f"Fake client exited: {fake.name} (PID: {pid})")

    def _SyncFakeClients(self):
        """Sync tracked processes with actual localhost clients in server.
        This cleans up orphaned clients (in server but no process) and
        orphaned processes (process running but not in server)."""
        localhost_in_server = len(self._GetLocalhostClients())
        tracked_processes = len(self._fakeClients)

        # If there are more localhost clients in server than tracked processes,
        # kick the extras (orphaned clients)
        while localhost_in_server > tracked_processes:
            localhost_clients = self._GetLocalhostClients()
            if localhost_clients:
                cl = localhost_clients[0]
                Log.warning(f"Kicking orphaned localhost client: {cl.GetName()} (ID: {cl.GetId()})")
                self._serverData.interface.ClientKick(cl.GetId())
                localhost_in_server -= 1
            else:
                break

        # If there are more tracked processes than localhost clients in server,
        # terminate the extras (orphaned processes)
        while tracked_processes > localhost_in_server and self._fakeClients:
            oldest_pid = min(self._fakeClients.keys(),
                             key=lambda p: self._fakeClients[p].spawn_time)
            fake = self._fakeClients.pop(oldest_pid)
            Log.warning(f"Terminating orphaned process: {fake.name} (PID: {oldest_pid})")
            fake.terminate()
            tracked_processes -= 1

    def _GetMatchedFakeClientCount(self) -> int:
        """Count fake clients that have confirmed PID <-> client_id match"""
        return sum(1 for f in self._fakeClients.values() if f.connected and f.client_id is not None)

    def _UpdateClientBalance(self):
        """Adjust fake client count based on real player count.

        This is called every tick and handles:
        1. Removing excess matched fake clients when real players join
        2. Spawning new fake clients when real players leave
        """
        if not self._runtimeEnabled:
            return

        if not self._IsServerRunning():
            return

        max_fake = self.config.cfg.get("maxFakeClients", 8)
        real_count = self._GetRealPlayerCount()
        matched_fake = self._GetMatchedFakeClientCount()
        tracked_fake = len(self._fakeClients)

        # Target: max_fake - real_count, but never negative
        target_fake = max(0, max_fake - real_count)

        # Remove excess MATCHED fake clients (only remove those we can safely match)
        # This handles the case where a real player joined while fakes were still connecting
        while matched_fake > target_fake:
            if self._KickOneMatchedFakeClient():
                matched_fake -= 1
                tracked_fake -= 1
            else:
                break

        # Only spawn if we have fewer tracked processes than target
        # AND enough time has passed since last spawn
        if tracked_fake < target_fake:
            if self._CanSpawnNow():
                Log.debug(f"Spawning: tracked={tracked_fake}, matched={matched_fake}, target={target_fake}, real={real_count}")
                self._SpawnFakeClient()
            else:
                # Still waiting for spawn delay
                pass

    def Start(self) -> bool:
        """Called when plugin starts"""
        if not self._IsWindows():
            Log.warning("AutoClient plugin disabled: Not running on Windows")
            self._runtimeEnabled = False
            return True  # Return True so plugin loads but does nothing

        if not self.config.cfg.get("enabled", True):
            Log.info("AutoClient plugin disabled by config")
            self._runtimeEnabled = False
            return True

        if not self._IsServerRunning():
            Log.warning("AutoClient: Server process not detected, will wait for it to start")

        # Set sv_maxconnections to match maxFakeClients
        max_fake = self.config.cfg.get("maxFakeClients", 8)
        self._serverData.interface.SetCvar("sv_maxconnections", str(max_fake))
        Log.info(f"Set sv_maxconnections to {max_fake}")

        # Set g_anticheat to 0 if it's currently 1
        current_anticheat = self._serverData.interface.GetCvar("g_anticheat")
        if current_anticheat == "1":
            self._serverData.interface.SetCvar("g_anticheat", "0")
            Log.info("Set g_anticheat to 0")

        Log.info("AutoClient Plugin started")
        return True

    def DoLoop(self):
        """Called each server tick"""
        if not self._runtimeEnabled:
            return

        # Check health of existing clients
        self._CheckClientHealth()

        # Update balance
        self._UpdateClientBalance()

    def Finish(self):
        """Called when plugin shuts down"""
        if not IS_WINDOWS:
            return

        # Use PowerShell to force kill all mbii.x86.exe processes
        # This is more reliable than trying to kick/terminate individually
        try:
            subprocess.run(
                ["powershell", "-Command", "Stop-Process -Name 'mbii.x86' -Force -ErrorAction SilentlyContinue"],
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=10
            )
            Log.info("AutoClient cleanup: killed all mbii.x86.exe processes")
        except Exception as e:
            Log.error(f"Error during cleanup: {e}")

        self._fakeClients.clear()

    def _MatchFakeClientByName(self, client_name: str, client_id: int) -> bool:
        """Match a connecting localhost client to a tracked process by name"""
        for pid, fake in self._fakeClients.items():
            if not fake.connected:
                # Try to match by name (exact or partial)
                if fake.name == client_name or fake.name in client_name or client_name in fake.name:
                    fake.client_id = client_id
                    fake.connected = True
                    Log.info(f"Matched fake client: {client_name} (ID: {client_id}) -> PID {pid}")
                    return True
        return False

    def _GetFakeClientByClientId(self, client_id: int):
        """Find a tracked fake client by its in-game client ID"""
        for pid, fake in self._fakeClients.items():
            if fake.client_id == client_id:
                return pid, fake
        return None, None

    def _RemoveFakeClientByClientId(self, client_id: int) -> bool:
        """Remove a fake client by its in-game client ID - kicks and terminates"""
        pid, fake = self._GetFakeClientByClientId(client_id)
        if fake:
            Log.info(f"Removing fake client by ID: {fake.name} (ID: {client_id}, PID: {pid})")
            self._serverData.interface.ClientKick(client_id)
            fake.terminate()
            del self._fakeClients[pid]
            return True
        return False

    def OnClientConnect(self, eventClient: client.Client) -> bool:
        """Handle player connect"""
        if not self._runtimeEnabled:
            return False

        client_ip = eventClient.GetIp()
        client_name = eventClient.GetName()
        client_id = eventClient.GetId()

        if self._IsLocalhost(client_ip):
            # This is a fake client connecting - match it to a tracked process
            if self._MatchFakeClientByName(client_name, client_id):
                Log.info(f"Fake client connected and matched: {client_name} (ID: {client_id})")
            else:
                Log.warning(f"Localhost client connected but no matching process: {client_name} (ID: {client_id})")
        else:
            # Real player connected - remove a fake client to make room
            Log.info(f"Real player connected: {client_name} from {client_ip}")

            # ONLY remove a fake client if we have a confirmed PID <-> client_id match
            # This ensures we kick exactly the client whose process we terminate
            removed = False
            for pid, fake in list(self._fakeClients.items()):
                if fake.connected and fake.client_id is not None:
                    Log.info(f"Removing matched fake client: {fake.name} (ID: {fake.client_id}, PID: {pid})")
                    # Kick by client_id (removes from server) and terminate by PID (kills process)
                    # These are guaranteed to be the same client
                    self._serverData.interface.ClientKick(fake.client_id)
                    fake.terminate()
                    del self._fakeClients[pid]
                    removed = True
                    break

            if not removed:
                # No matched fake clients available
                # Log but don't blindly remove - wait for fake clients to connect and match
                unmatched_count = sum(1 for f in self._fakeClients.values() if not f.connected)
                Log.warning(f"No matched fake clients to remove. Unmatched processes: {unmatched_count}")
                # The balance will be corrected once fake clients finish connecting

        return False

    def OnClientDisconnect(self, eventClient: client.Client, reason: int) -> bool:
        """Handle player disconnect"""
        if not self._runtimeEnabled:
            return False

        client_ip = eventClient.GetIp()
        client_id = eventClient.GetId()
        client_name = eventClient.GetName()

        # If a fake client disconnected (localhost), terminate its process
        if self._IsLocalhost(client_ip):
            Log.debug(f"Fake client disconnected: {client_name} (ID: {client_id}, reason: {reason})")

            # First try to find by client ID (most reliable)
            pid, fake = self._GetFakeClientByClientId(client_id)
            if fake:
                Log.info(f"Terminating disconnected fake client by ID: {fake.name} (PID: {pid})")
                fake.terminate()
                del self._fakeClients[pid]
            else:
                # Fallback: find by name
                for pid, fake in list(self._fakeClients.items()):
                    if fake.name == client_name or fake.name in client_name or client_name in fake.name:
                        Log.info(f"Terminating disconnected fake client by name: {fake.name} (PID: {pid})")
                        fake.terminate()
                        del self._fakeClients[pid]
                        break
        else:
            # Real player left, we may need to spawn more fakes
            real_count = self._GetRealPlayerCount() - 1  # Subtract 1 because they're still counted
            Log.debug(f"Real player disconnected: {client_name}. Real count will be: {real_count}")
            # Balance will be updated in DoLoop

        return False

    # SMOD Command Handlers

    def HandleToggle(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """Toggle plugin on/off"""
        if not self._IsWindows():
            self._serverData.interface.SmSay(self._messagePrefix + "^1Cannot enable: Not running on Windows")
            return True

        self._runtimeEnabled = not self._runtimeEnabled
        state = "^2ENABLED" if self._runtimeEnabled else "^1DISABLED"
        self._serverData.interface.SmSay(self._messagePrefix + f"AutoClient {state}")

        if not self._runtimeEnabled:
            count = self._RemoveAllFakeClients()
            if count > 0:
                self._serverData.interface.SmSay(self._messagePrefix + f"Terminated {count} fake client(s)")

        Log.info(f"SMOD {smodID} toggled AutoClient: {self._runtimeEnabled}")
        return True

    def HandleStatus(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """Show current status"""
        real_count = self._GetRealPlayerCount()
        fake_tracked = len(self._fakeClients)
        fake_ingame = self._GetFakePlayerCount()
        max_fake = self.config.cfg.get("maxFakeClients", 8)
        server_running = self._IsServerRunning()

        status = "^2ENABLED" if self._runtimeEnabled else "^1DISABLED"
        server_status = "^2Running" if server_running else "^1Not Running"

        self._serverData.interface.SmSay(self._messagePrefix + f"Status: {status}")
        self._serverData.interface.SmSay(self._messagePrefix + f"Server Process: {server_status}")
        self._serverData.interface.SmSay(self._messagePrefix + f"Real Players: ^2{real_count}")
        self._serverData.interface.SmSay(self._messagePrefix + f"Fake Clients: ^3{fake_tracked} tracked, {fake_ingame} in-game")
        self._serverData.interface.SmSay(self._messagePrefix + f"Max Fake: ^5{max_fake}")
        return True

    def HandleSpawnFake(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """Manually spawn fake clients"""
        if not self._IsWindows():
            self._serverData.interface.SmSay(self._messagePrefix + "^1Cannot spawn: Not running on Windows")
            return True

        if not self._IsServerRunning():
            self._serverData.interface.SmSay(self._messagePrefix + "^1Cannot spawn: Server process not running")
            return True

        count = 1
        if len(cmdArgs) > 1:
            try:
                count = int(cmdArgs[1])
                count = max(1, min(count, 10))  # Limit to 1-10
            except ValueError:
                self._serverData.interface.SmSay(self._messagePrefix + "Usage: !spawnfake <count>")
                return True

        spawned = 0
        for _ in range(count):
            if self._SpawnFakeClient():
                spawned += 1

        self._serverData.interface.SmSay(self._messagePrefix + f"Spawned {spawned} fake client(s)")
        Log.info(f"SMOD {smodID} manually spawned {spawned} fake clients")
        return True

    def HandleKillFakes(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """Kill all fake clients"""
        count = self._RemoveAllFakeClients()
        self._serverData.interface.SmSay(self._messagePrefix + f"Terminated {count} fake client(s)")
        Log.info(f"SMOD {smodID} killed all fake clients ({count})")
        return True

    def HandleSmodCommand(self, playerName: str, smodID: int, adminIP: str, cmdArgs: list) -> bool:
        """Dispatch SMOD commands"""
        command = cmdArgs[0]
        if command.startswith("!"):
            command = command[1:]

        for aliases, (help_text, handler) in self._smodCommandList.items():
            if command in aliases:
                return handler(playerName, smodID, adminIP, cmdArgs)

        return False

    def OnSmsay(self, playerName: str, smodID: int, adminIP: str, message: str) -> bool:
        """Handle SMOD smsay commands"""
        if not message.startswith("!"):
            return False

        cmdArgs = message.split()
        return self.HandleSmodCommand(playerName, smodID, adminIP, cmdArgs)


# Plugin lifecycle functions

def OnInitialize(serverData: serverdata.ServerData, exports=None):
    """Initialize the plugin"""
    global SERVER_DATA, PluginInstance

    SERVER_DATA = serverData
    PluginInstance = AutoClientPlugin(serverData)

    # Register SMOD commands
    registeredSmodCommands = serverData.GetServerVar("registeredSmodCommands") or []
    for aliases, (help_text, handler) in PluginInstance._smodCommandList.items():
        for alias in aliases:
            registeredSmodCommands.append((alias, help_text))
    serverData.SetServerVar("registeredSmodCommands", registeredSmodCommands)

    return True


def OnStart() -> bool:
    """Called after plugin initialization"""
    startTime = time()
    result = PluginInstance.Start()
    if result and IS_WINDOWS:
        loadTime = time() - startTime
        PluginInstance._serverData.interface.SvSay(
            PluginInstance._messagePrefix + f"AutoClient started in {loadTime:.2f} seconds!"
        )
    return result


def OnLoop():
    """Called on each server tick"""
    PluginInstance.DoLoop()


def OnFinish():
    """Called before plugin unload"""
    PluginInstance.Finish()


def OnEvent(event) -> bool:
    """Handle server events"""
    global PluginInstance

    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return PluginInstance.OnClientConnect(event.client)

    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return PluginInstance.OnClientDisconnect(event.client, event.reason)

    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return PluginInstance.OnSmsay(event.playerName, event.smodID, event.adminIP, event.message)

    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_WD_DIED:
        # Server process died - kill all fake clients
        count = PluginInstance._RemoveAllFakeClients()
        if count > 0:
            Log.info(f"Server process died - terminated {count} fake client(s)")
        return False

    return False


if __name__ == "__main__":
    print("This is a plugin for the Godfinger Movie Battles II plugin system.")
    print("Please run one of the start scripts in the start directory to use it.")
    input("Press Enter to close this message.")
    exit()
