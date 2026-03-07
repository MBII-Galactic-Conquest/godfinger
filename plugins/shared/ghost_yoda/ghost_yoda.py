import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import lib.shared.teams as teams
import godfingerEvent

import threading
import logging
import asyncio
import discord
import os
import time
from collections import deque
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Initialize the Logger
Log = logging.getLogger(__name__)

# Global variables
SERVER_DATA = None
bot_thread = None
shutdown_event = threading.Event()
log_watcher_task = None

# Chat bridge rate limiting state
# Global: deque of timestamps, max 5 messages per 5 seconds
_bridge_global_timestamps = deque()
_BRIDGE_GLOBAL_LIMIT = 5
_BRIDGE_GLOBAL_WINDOW = 5.0
# Per-user: dict of {user_id: deque of timestamps}, max 3 messages per 3 seconds
_bridge_user_timestamps = {}
_BRIDGE_USER_LIMIT = 1
_BRIDGE_USER_WINDOW = 1.0
# Per-user block tracking: {user_id: unblock_time}
_bridge_user_blocked = {}

# Define intents
intents = discord.Intents.default()
intents.message_content = True  # Privileged intent - must be enabled in Discord Developer Portal

# Initialize Discord client
client = discord.Client(intents=intents)

# Environmental variables
DISCORD_BOT_TOKEN = None
DISCORD_GUILD_ID = None
DISCORD_LINK = None
DISCORD_CHANNEL_REPORTS = None
DISCORD_CHANNEL_BANNED_ENTRY = None
DISCORD_CHANNEL_ADMIN_ACTIONS = None
DISCORD_CHANNEL_SERVER_CHAT_LOGS = None
DISCORD_CHAT_BRIDGE_MODE = None
DISCORD_CHAT_BRIDGE_PREFIX = None

class GhostYodaPlugin(object):
    def __init__(self, serverData: serverdata.ServerData) -> None:
        self._serverData: serverdata.ServerData = serverData
        self._messagePrefix = colors.ColorizeText("[YODA]", "green") + ": "
        
        # TK Tracking structure: dict mapped by client_id holding a list of {"time": datetime, "victim_name": str}
        self.tk_history = {}
        
        # Commands dict
        self._commandList = {
            teams.TEAM_GLOBAL: {
                tuple(["discord"]): ("!discord - Get the server's Discord link", self.HandleDiscordCommand),
                tuple(["report"]): ("!report <target> <reason> - Report a player to the Discord admins", self.HandleReportCommand)
            },
            teams.TEAM_EVIL: {},
            teams.TEAM_GOOD: {},
            teams.TEAM_SPEC: {}
        }

    def HandleDiscordCommand(self, player, args, messageRaw):
        if DISCORD_LINK and DISCORD_LINK != "your_discord_link_here":
            self._serverData.interface.SvSay(self._messagePrefix + f"^7Join our Discord! ^5{DISCORD_LINK}")
        else:
            self._serverData.interface.SvSay(self._messagePrefix + "^7Discord link has not been configured yet.")
        return True

    def ProcessKillEvent(self, event):
        """Track teamkills for the !report command and broadcast to Discord."""
        
        # Construct the kill string and dump it to Discord if someone died
        log_kill_str = colors.StripColorCodes(event.data.get("text", ""))
        msg = f"⚔️ {log_kill_str}"
        asyncio.run_coroutine_threadsafe(send_chat_log_to_discord(msg), client.loop)
        
        if not event.data.get("tk", False) or event.client is None or event.client == event.victim:
            return False
            
        killer_id = event.client.GetId()
        victim_name = event.victim.GetName()
        
        if killer_id not in self.tk_history:
            self.tk_history[killer_id] = []
            
        self.tk_history[killer_id].append({"time": datetime.now(), "victim_name": victim_name})
        
        # Prune old TKs (older than 10 minutes)
        cutoff_time = datetime.now() - timedelta(minutes=10)
        self.tk_history[killer_id] = [tk for tk in self.tk_history[killer_id] if tk["time"] > cutoff_time]
        
        return False

    def HandleReportCommand(self, player, args, messageRaw):
        if len(args) < 3:
            self._serverData.interface.SvTell(player.GetId(), self._messagePrefix + "^7Usage: !report <target name> <reason>")
            return True
            
        target_query = args[1].lower()
        reason = " ".join(args[2:])
        reporter_info = player.GetInfo()
        
        # Find the best match
        matched_client = None
        for cl in self._serverData.API.GetAllClients():
            if target_query in colors.StripColorCodes(cl.GetName()).lower():
                matched_client = cl
                break
                
        if not matched_client:
            self._serverData.interface.SvTell(player.GetId(), self._messagePrefix + f"^7Could not find a player matching '^1{target_query}^7'.")
            return True
            
        # Compile report
        target_id = matched_client.GetId()
        recent_tks = self.tk_history.get(target_id, [])
        
        report_data = {
            "server": self._serverData.name,
            "reporter_name": player.GetName(),
            "reporter_id": player.GetId(),
            "reporter_ip": player.GetIp(),
            "reporter_guid": getattr(player, "_jaguid", "Unknown ja_guid"),
            "reason": reason,
            "offender_name": matched_client.GetName(),
            "offender_id": target_id,
            "offender_ip": matched_client.GetIp(),
            "offender_guid": getattr(matched_client, "_jaguid", "Unknown ja_guid"),
            "recent_tks": recent_tks
        }
        
        asyncio.run_coroutine_threadsafe(
            send_report_to_discord(report_data),
            client.loop
        )
        self._serverData.interface.SvTell(player.GetId(), self._messagePrefix + f"^7Report against ^1{matched_client.GetName()}^7 submitted successfully.")
        return True

    def ProcessSmodCommand(self, event):
        """Forward smod commands to Discord."""
        data = event.data
        if not data or not data.get("command"):
            return False
            
        asyncio.run_coroutine_threadsafe(
            send_admin_action_to_discord(data),
            client.loop
        )
        return False

    def ProcessSmodLogin(self, event):
        """Forward smod logins to Discord."""
        data = {
            "smod_name": event.playerName,
            "smod_id": str(event.smodID),
            "smod_ip": event.adminIP,
            "command": "LOGIN"
        }
        
        asyncio.run_coroutine_threadsafe(
            send_admin_action_to_discord(data),
            client.loop
        )
        return False

    def HandleBannedEntryAttempt(self, event):
        """Forward banned entry attempts to Discord."""
        data = {
            "ip": event.ip
        }
        
        asyncio.run_coroutine_threadsafe(
            send_banned_entry_to_discord(data),
            client.loop
        )
        return False

    def ProcessServerSay(self, event):
        """Forward server say broadcasts to Discord."""
        msg = f"🖥️ say: Server: {event.message}"
        asyncio.run_coroutine_threadsafe(
            send_chat_log_to_discord(msg),
            client.loop
        )
        return False

    def ProcessClientConnect(self, event):
        """Forward client connects to Discord."""
        cl = event.client
        msg = f"✅ ClientConnect: ({colors.StripColorCodes(cl.GetName())}) ID: {cl.GetId()} (IP: {cl.GetIP()})"
        asyncio.run_coroutine_threadsafe(
            send_chat_log_to_discord(msg),
            client.loop
        )
        return False

    def ProcessClientDisconnect(self, event):
        """Forward client disconnects to Discord."""
        cl = event.client
        msg = f"❌ ClientDisconnect: {cl.GetId()}"
        asyncio.run_coroutine_threadsafe(
            send_chat_log_to_discord(msg),
            client.loop
        )
        return False

    def ProcessMessage(self, event):
        """Catch commands by routing through _commandList and broadcast to Discord."""
        
        # Construct the chat log string and dump it to Discord
        cl = event.client
        msg = f"💬 {cl.GetId()}: say: {colors.StripColorCodes(cl.GetName())}: \"{colors.StripColorCodes(event.message)}\""
        asyncio.run_coroutine_threadsafe(send_chat_log_to_discord(msg), client.loop)
        
        message_raw = colors.StripColorCodes(event.message).strip()
        player = event.client
        teamId = player.GetTeamId()
        
        cmdArgs = message_raw.split()
        if not cmdArgs:
            return False
            
        command = cmdArgs[0].lower()
        if command.startswith('!'):
            command = command[1:]
            
        # Check global commands
        for c in self._commandList.get(teams.TEAM_GLOBAL, {}):
            if command in c:
                return self._commandList[teams.TEAM_GLOBAL][c][1](player, cmdArgs, message_raw)
                
        # Check team specific commands
        for c in self._commandList.get(teamId, {}):
            if command in c:
                return self._commandList[teamId][c][1](player, cmdArgs, message_raw)

        return False

# --- Async Discord Functions ---
def load_env_variables():
    global DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_LINK, DISCORD_CHANNEL_REPORTS, DISCORD_CHANNEL_BANNED_ENTRY, DISCORD_CHANNEL_ADMIN_ACTIONS, DISCORD_CHANNEL_SERVER_CHAT_LOGS
    global DISCORD_CHAT_BRIDGE_MODE, DISCORD_CHAT_BRIDGE_PREFIX
    env_file = os.path.join(os.path.dirname(__file__), "ghost_yoda.env")

    if load_dotenv(env_file, override=True):
        DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
        DISCORD_LINK = os.getenv("DISCORD_LINK")
        DISCORD_CHANNEL_REPORTS = os.getenv("DISCORD_CHANNEL_REPORTS")
        DISCORD_CHANNEL_BANNED_ENTRY = os.getenv("DISCORD_CHANNEL_BANNED_ENTRY")
        DISCORD_CHANNEL_ADMIN_ACTIONS = os.getenv("DISCORD_CHANNEL_ADMIN_ACTIONS")
        DISCORD_CHANNEL_SERVER_CHAT_LOGS = os.getenv("DISCORD_CHANNEL_SERVER_CHAT_LOGS")
        DISCORD_CHAT_BRIDGE_MODE = os.getenv("DISCORD_CHAT_BRIDGE_MODE", "svsay").lower()
        DISCORD_CHAT_BRIDGE_PREFIX = os.getenv("DISCORD_CHAT_BRIDGE_PREFIX", "[Discord]")
        print("Required environmental variables for Ghost Yoda loaded!")
    else:
        print("Unable to load ghost_yoda.env. It may not exist!")

async def start_discord_bot():
    await client.start(DISCORD_BOT_TOKEN)

def start_discord_bot_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(client.start(DISCORD_BOT_TOKEN))
    except Exception as e:
        Log.error(f"Error starting Ghost Yoda bot: {e}")
    finally:
        loop.run_until_complete(client.close())
        loop.stop()
        loop.close()

def stop_bot_thread():
    global bot_thread, log_watcher_task
    if bot_thread and bot_thread.is_alive():
        shutdown_event.set()
        if log_watcher_task:
            future_cancel = asyncio.run_coroutine_threadsafe(log_watcher_task.cancel(), client.loop)
            try:
                future_cancel.result(timeout=1)
            except asyncio.TimeoutError:
                pass
            log_watcher_task = None

        future = asyncio.run_coroutine_threadsafe(client.close(), client.loop)
        try:
            future.result(timeout=5)
            bot_thread.join(timeout=5)
        except Exception:
            pass
        bot_thread = None

async def tail_bans_log():
    """Scaffolding for catching IP banned messages in the system console."""
    while not shutdown_event.is_set():
        # TODO: Implement reading from QConsole output or reading a dedicated log file
        await asyncio.sleep(1)

@client.event
async def on_ready():
    Log.info(f'Ghost Yoda logged in as {client.user}')
    global log_watcher_task
    log_watcher_task = asyncio.create_task(tail_bans_log())

@client.event
async def on_message(message):
    """Relay Discord messages from #server-chat-logs to the game server."""
    # Ignore bot messages (prevents looping our own relay messages back into the game)
    if message.author.bot:
        return

    # Only relay messages sent in the configured chat bridge channel
    if not DISCORD_CHANNEL_SERVER_CHAT_LOGS:
        return
    if message.channel.id != int(DISCORD_CHANNEL_SERVER_CHAT_LOGS):
        return
    
    if not SERVER_DATA:
        return

    # Strip newlines and non-ascii characters, cap length
    raw = message.content.replace('\n', ' ').strip()
    raw = raw.encode("ascii", "ignore").decode("ascii")
    if not raw:
        return
    if len(raw) > 150:
        raw = raw[:147] + "..."

    now = time.monotonic()
    user_id = message.author.id

    # --- Per-user rate limit: 3 messages per 3 seconds ---
    # Check if user is currently blocked
    unblock_time = _bridge_user_blocked.get(user_id)
    if unblock_time is not None:
        if now < unblock_time:
            remaining = round(unblock_time - now, 1)
            try:
                await message.reply(
                    f"⛔ You are sending messages too fast! Please wait **{remaining}s** before sending again.",
                    delete_after=6
                )
                await message.delete()
            except Exception:
                pass
            return
        else:
            del _bridge_user_blocked[user_id]

    # Track this user's timestamps
    if user_id not in _bridge_user_timestamps:
        _bridge_user_timestamps[user_id] = deque()
    user_ts = _bridge_user_timestamps[user_id]
    # Prune expired entries
    while user_ts and now - user_ts[0] > _BRIDGE_USER_WINDOW:
        user_ts.popleft()
    
    if len(user_ts) >= _BRIDGE_USER_LIMIT:
        # Block user until the oldest entry in their window expires
        unblock_at = user_ts[0] + _BRIDGE_USER_WINDOW
        _bridge_user_blocked[user_id] = unblock_at
        remaining = round(unblock_at - now, 1)
        try:
            await message.reply(
                f"⛔ You are sending messages too fast! Please wait **{remaining}s** before sending again.",
                delete_after=6
            )
            await message.delete()
        except Exception:
            pass
        return

    user_ts.append(now)

    # --- Global rate limit: 5 messages per 5 seconds ---
    # Prune expired global entries
    while _bridge_global_timestamps and now - _bridge_global_timestamps[0] > _BRIDGE_GLOBAL_WINDOW:
        _bridge_global_timestamps.popleft()
    
    global_saturated = len(_bridge_global_timestamps) >= _BRIDGE_GLOBAL_LIMIT
    _bridge_global_timestamps.append(now)

    # Build and relay the message
    prefix = DISCORD_CHAT_BRIDGE_PREFIX or "[Discord]"
    sender = message.author.display_name
    game_msg = f"{prefix} ^5{sender}^7: {raw}"

    # When global limit is saturated, fall back to say (quieter)
    if global_saturated or DISCORD_CHAT_BRIDGE_MODE == "say":
        SERVER_DATA.interface.Say(game_msg)
    else:
        SERVER_DATA.interface.SvSay(game_msg)

async def send_report_to_discord(report_data):
    if not client.is_ready() or not DISCORD_CHANNEL_REPORTS or DISCORD_CHANNEL_REPORTS == "your_reports_id_here":
        return
        
    guild = client.get_guild(int(DISCORD_GUILD_ID))
    if not guild: return
    channel = guild.get_channel(int(DISCORD_CHANNEL_REPORTS))
    if not channel: return
    
    # Format message matching the user specs perfectly
    msg = f"**Server:** `{report_data['server']}`\n"
    msg += f"**Reporter:** `{report_data['reporter_name']}` ( {report_data['reporter_id']} | {report_data['reporter_ip']} | {report_data.get('reporter_guid', 'Unknown')} )\n"
    msg += f"**Reason:**    {report_data['reason']}\n"
    msg += f"**Offender:** `{report_data['offender_name']}` ( {report_data['offender_id']} | {report_data['offender_ip']} | {report_data.get('offender_guid', 'Unknown')} )\n\n"
    
    if report_data['recent_tks']:
        msg += "**Offender's latest team kills are:**\n\n"
        for tk in reversed(report_data['recent_tks']):
            time_diff = int((datetime.now() - tk['time']).total_seconds())
            mins, secs = divmod(time_diff, 60)
            time_str = f"{mins}m {secs}s ago" if mins > 0 else f"{secs}s ago"
            
            # Use backticks for proper quoting the same way Yoda did
            msg += f"`{report_data['offender_name']}` ( {report_data['offender_id']} | {report_data['offender_ip']} | {report_data.get('offender_guid', 'Unknown')} ) - {tk['victim_name']} - {time_str}\n"

        # Tally out the TKs if any are against the reporter
        count_against_reporter = sum(1 for tk in report_data['recent_tks'] if tk['victim_name'] == report_data['reporter_name'])
        total_tks = len(report_data['recent_tks'])
        if count_against_reporter > 0:
            msg += f"\nThe reporter has been team killed by them {count_against_reporter} times out of the {total_tks} team kills they have done in the last 10 minutes.\n"
    else:
        msg += "\nOffender has no recent team kills logged in the past 10 minutes.\n"
        
    await channel.send(msg)

async def send_admin_action_to_discord(admin_data):
    if not client.is_ready() or not DISCORD_CHANNEL_ADMIN_ACTIONS or DISCORD_CHANNEL_ADMIN_ACTIONS == "your_admin_actions_id_here":
        return

    guild = client.get_guild(int(DISCORD_GUILD_ID))
    if not guild: return
    channel = guild.get_channel(int(DISCORD_CHANNEL_ADMIN_ACTIONS))
    if not channel: return

    # Admin action format matching user specified
    smod_name = admin_data.get('smod_name', 'Unknown')
    smod_id = admin_data.get('smod_id', 'Unknown')
    smod_ip = admin_data.get('smod_ip', 'Unknown')
    command = admin_data.get('command', 'Unknown')
    args = admin_data.get('args', '')
    
    target_str = ""
    if admin_data.get('target_name'):
        target_name = admin_data.get('target_name')
        target_ip = admin_data.get('target_ip', '')
        target_str = f"__Target:__    `{target_name}` {target_ip}"

    msg = f"__Server:__    `{SERVER_DATA.name}`\n"
    msg += f"__Admin:__     `{smod_name}` **[SMOD ID: {smod_id}]** {smod_ip}\n"
    
    if args:
        msg += f"__Command:__   **{command} {args}**\n"
    else:
        msg += f"__Command:__   **{command}**\n"
        
    if target_str:
        msg += f"{target_str}\n"

    await channel.send(msg)

async def send_banned_entry_to_discord(banned_data):
    if not client.is_ready() or not DISCORD_CHANNEL_BANNED_ENTRY or DISCORD_CHANNEL_BANNED_ENTRY == "your_banned_entry_id_here":
        return

    guild = client.get_guild(int(DISCORD_GUILD_ID))
    if not guild: return
    channel = guild.get_channel(int(DISCORD_CHANNEL_BANNED_ENTRY))
    if not channel: return

    ip = banned_data.get('ip', 'Unknown IP')
    
    msg = f"**Banned Entry Attempt**\n"
    msg += f"**IP:** `{ip}`\n"
    msg += f"**Server:** `{SERVER_DATA.name}`\n"

    await channel.send(msg)

async def send_chat_log_to_discord(log_msg):
    if not client.is_ready() or not DISCORD_CHANNEL_SERVER_CHAT_LOGS or DISCORD_CHANNEL_SERVER_CHAT_LOGS == "your_server_chat_logs_id_here":
        return

    guild = client.get_guild(int(DISCORD_GUILD_ID))
    if not guild: return
        
    channel = guild.get_channel(int(DISCORD_CHANNEL_SERVER_CHAT_LOGS))
    if not channel: return

    # Grab Godfinger's standard time string for Discord like [2025-11-05 21:05:38 HST]
    time_str = datetime.now().strftime("[%Y-%m-%d %H:%M:%S EST]")
    full_msg = f"`{time_str}` {log_msg}"
        
    await channel.send(full_msg)

# --- Godfinger Framework Hooks ---
def OnInitialize(serverData: serverdata.ServerData, exports=None) -> bool:
    global SERVER_DATA, PluginInstance
    SERVER_DATA = serverData
    load_env_variables()
    PluginInstance = GhostYodaPlugin(serverData)
    
    # Register command help mapping
    newVal = []
    rCommands = SERVER_DATA.GetServerVar("registeredCommands")
    if rCommands != None:
        newVal.extend(rCommands)
    for cmd in PluginInstance._commandList[teams.TEAM_GLOBAL]:
        for alias in cmd:
            if not alias.isdecimal():
                newVal.append((alias, PluginInstance._commandList[teams.TEAM_GLOBAL][cmd][0]))
    SERVER_DATA.SetServerVar("registeredCommands", newVal)
    
    return True

def OnStart():
    global bot_thread
    if DISCORD_BOT_TOKEN and DISCORD_BOT_TOKEN != "your_token_here":
        bot_thread = threading.Thread(target=start_discord_bot_thread, daemon=True)
        bot_thread.start()
        print("Ghost Yoda Discord bot thread started!")
    else:
        print("Ghost Yoda bot token is missing. Bot will not start.")
    return True

def OnLoop():
    pass

def OnFinish():
    stop_bot_thread()

def OnEvent(event) -> bool:
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return PluginInstance.ProcessMessage(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return PluginInstance.ProcessKillEvent(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMOD_COMMAND:
        return PluginInstance.ProcessSmodCommand(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMOD_LOGIN:
        return PluginInstance.ProcessSmodLogin(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_BANNED_ENTRY_ATTEMPT:
        return PluginInstance.HandleBannedEntryAttempt(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SERVER_SAY:
        return PluginInstance.ProcessServerSay(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return PluginInstance.ProcessClientConnect(event)
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return PluginInstance.ProcessClientDisconnect(event)
    return False

if __name__ == "__main__":
    print("This is Ghost Yoda for Godfinger.")
    exit()
