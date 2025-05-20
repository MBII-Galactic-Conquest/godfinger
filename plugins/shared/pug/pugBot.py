import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import lib.shared.client as client

import discord
from discord.ext import commands, tasks
from discord.utils import get
from datetime import datetime, timedelta
from dotenv import load_dotenv
import threading
import time
import asyncio
import os

SERVER_DATA = None;
Log = logging.getLogger(__name__);

# Environment File
env_file = os.path.join(os.path.dirname(__file__), "pugConfig.env")

def check_and_create_env():
    if not os.path.exists(env_file):
        print(f"{env_file} not found. Creating a new one with default values.")
        with open(env_file, 'w') as f:
            f.write("""
# Queue Configuration
QUEUE_TIMEOUT=1800  # 30 minutes in seconds
MAX_QUEUE_SIZE=10
MIN_QUEUE_SIZE=6

# Discord Configuration
BOT_TOKEN=
PUG_ROLE_ID=
ADMIN_ROLE_ID=
ALLOWED_CHANNEL_ID=
SERVER_PASSWORD=password
            """)
        load_dotenv(dotenv_path=env_file)

    if os.path.exists(env_file):
        load_dotenv(dotenv_path=env_file)
        print(f"Environment variables loaded from {env_file}")

# List of environment variables to reset
env_vars_to_reset = [
    "QUEUE_TIMEOUT", "MAX_QUEUE_SIZE", "MIN_QUEUE_SIZE", 
    "BOT_TOKEN", "PUG_ROLE_ID", "ADMIN_ROLE_ID", 
    "ALLOWED_CHANNEL_ID", "SERVER_PASSWORD"
]

def reset_env_vars(vars_list):
    # Reset the environment variables
    for var in vars_list:
        os.environ.pop(var, None)  # None prevents KeyError if the variable doesn't exist

    # Print the reset values in columns
    print(f"{'Variable':<25}{'Reset Status'}")
    print('-' * 40)
    for var in vars_list:
        status = 'Reset' if var not in os.environ else 'Not Reset'
        print(f"{var:<25}{status}")

reset_env_vars(env_vars_to_reset);

check_and_create_env();

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# === Config from .env ===
QUEUE_TIMEOUT = int(os.getenv("QUEUE_TIMEOUT"))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE"))
MIN_QUEUE_SIZE = int(os.getenv("MIN_QUEUE_SIZE"))

BOT_TOKEN = os.getenv("BOT_TOKEN")  # Keep as str
PUG_ROLE_ID = int(os.getenv("PUG_ROLE_ID"))
ADMIN_ROLE_ID = int(os.getenv("ADMIN_ROLE_ID"))
ALLOWED_CHANNEL_ID = int(os.getenv("ALLOWED_CHANNEL_ID"))
SERVER_PASSWORD = os.getenv("SERVER_PASSWORD")

# === Queue State ===
player_queue = []
queue_created_time = None
last_join_time = None

class pugBotPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData : serverdata.ServerData = serverData
        self._messagePrefix = colors.ColorizeText("[PUG]", "lblue") + ": "


@tasks.loop(seconds=30)
async def monitor_queue_task():
    global player_queue, last_join_time

    if not player_queue or not last_join_time:
        return

    if (datetime.utcnow() - last_join_time) > timedelta(seconds=QUEUE_TIMEOUT):
        channel = bot.get_channel(ALLOWED_CHANNEL_ID)
        if channel:
            await channel.send("**Queue timed out due to inactivity!**\n> Clearing queue...")
        player_queue.clear()

@bot.event
async def on_ready():
    print(f"Bot connected as {bot.user}")
    if not monitor_queue_task.is_running():
        monitor_queue_task.start()

# === Queue Command Group ===
@bot.group()
async def queue(ctx):
    if ctx.invoked_subcommand is None:
        await ctx.send("Available subcommands: `join`, `leave`, `status`, `start`, `forcestart`.")

@queue.command(name='join')
async def queue_join(ctx):
    global player_queue, queue_created_time, last_join_time

    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        return

    user = ctx.author
    if user in player_queue:
        await ctx.send(f"{user.mention}, you're already in the queue!\n> (`{len(player_queue)}/{MAX_QUEUE_SIZE}`)")
        return

    if not player_queue:
        queue_created_time = datetime.utcnow()
        pug_mention = f"<@&{PUG_ROLE_ID}>"
        await ctx.send(f"{user.mention} started a new queue! {pug_mention}\n> `{MIN_QUEUE_SIZE}` players required to `!queue start` without admin.")

    player_queue.append(user)
    last_join_time = datetime.utcnow()

    needed = MAX_QUEUE_SIZE - len(player_queue)
    await ctx.send(f"{user.mention} has joined the queue!\n> (`{len(player_queue)}/{MAX_QUEUE_SIZE}`, `{needed}` more to start)")

    if len(player_queue) >= MAX_QUEUE_SIZE:
        await start_queue(ctx.channel)

@queue.command(name='leave')
async def queue_leave(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        return

    user = ctx.author
    if user in player_queue:
        player_queue.remove(user)

        if not player_queue:
            await ctx.send(f"{user.mention} has left the queue!\n> **The queue is now empty and has been cancelled.**")
        else:
            needed = MAX_QUEUE_SIZE - len(player_queue)
            await ctx.send(f"{user.mention} has left the queue!\n> (`{len(player_queue)}/{MAX_QUEUE_SIZE}`, `{needed}` more to start)")
    else:
        await ctx.send(f"{user.mention}, you're not in the queue!")

@queue.command(name='status')
async def queue_status(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        return

    if not player_queue:
        await ctx.send("**The queue is currently empty!**")
    else:
        names = [user.mention for user in player_queue]
        formatted_names = "\n".join([f"{i+1}. {name}" for i, name in enumerate(names)])

        # Time remaining calculation
        time_left_str = ""
        if last_join_time:
            time_elapsed = (datetime.utcnow() - last_join_time).total_seconds()
            time_left = max(0, QUEUE_TIMEOUT - int(time_elapsed))
            minutes, seconds = divmod(time_left, 60)
            time_left_str = f"\n> Queue will expire in *(mm:ss)* `{int(minutes):02d}:{int(seconds):02d}` ..."

        await ctx.send(
            f"Queue Status:\n"
            f"> `{len(player_queue)}` player(s) in queue.{time_left_str}\n\n"
            f"{formatted_names}"
        )

@queue.command(name='start')
async def start_command(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        return

    if len(player_queue) >= MIN_QUEUE_SIZE and len(player_queue) % 2 == 0:
        await start_queue(ctx.channel)
    else:
        await ctx.send(
            f"**Not enough players to start the queue!**\n"
            f"> Minimum required: `{MIN_QUEUE_SIZE}`\n"
            f"> Current players: `{len(player_queue)}`\n"
            f"*You need an even number of players to form balanced teams...*"
        )

@queue.command(name='forcestart')
async def force_start(ctx):
    print(f"Force start command triggered by {ctx.author.name}")  # Debug log
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        return

    if ADMIN_ROLE_ID not in [role.id for role in ctx.author.roles]:
        await ctx.send("**You don't have permission to use this command!**")
        return

    await start_queue(ctx.channel)

async def start_queue(channel):
    global player_queue
    role_mention = f"<@&{PUG_ROLE_ID}>"

    message = "**Queue started!**\n"
    message += f"> {role_mention}\n\n"

    # Enumerate and list users
    message += "\n".join([f"{i+1}. {user.mention}" for i, user in enumerate(player_queue)])

    await channel.send(message)
    player_queue.clear()

# === Miscellaneous Commands ===
@bot.command(name='pw')
async def password_command(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        return
    await ctx.send(f"Server password: `{SERVER_PASSWORD}`")

@bot.command(name='password')
async def password_alias(ctx):
    await password_command(ctx)

async def queue_server_empty(content):
    channel = bot.get_channel(ALLOWED_CHANNEL_ID)
    if channel:
        await channel.send(content)

# Called once when this module ( plugin ) is loaded, return is bool to indicate success for the system
def OnInitialize(serverData : serverdata.ServerData, exports = None) -> bool:
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

    global SERVER_DATA;
    SERVER_DATA = serverData; # keep it stored
    if exports != None:
        pass;
    global PluginInstance;
    PluginInstance = pugBotPlugin(serverData)

    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    startTime = time.time()
    loadTime = time.time() - startTime
    PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + f"PUGBot started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system
def OnLoop():
    pass

# Called before the plugin is unloaded by the system
def OnFinish():
    pass

# Called from system on some event raising, return True to indicate event being captured in this module, False to continue tossing it to other plugins in chain
def OnEvent(event) -> bool:
    #print("Calling OnEvent function from plugin with event %s!" % (str(event)));
    if event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MESSAGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCONNECT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENT_BEGIN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTCHANGED:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_CLIENTDISCONNECT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SERVER_EMPTY:
        global player_queue
        channel = bot.get_channel(ALLOWED_CHANNEL_ID)

        if player_queue:
            Log.info("Server is empty, clearing the active PUG queue.")
            last_join_time = None
            asyncio.run_coroutine_threadsafe(
                queue_server_empty(
                    "**All players have disconnected from the game server.**\n> Clearing the active PUG queue..."
                ),
                bot.loop
            )
            player_queue.clear()
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SHUTDOWN:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_KILL:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_EXIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_MAPCHANGE:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_SMSAY:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_POST_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_REAL_INIT:
        return False;
    elif event.type == godfingerEvent.GODFINGER_EVENT_TYPE_PLAYER_SPAWN:
        return False;

    return False;

# === Run the Bot ===
def run_bot():
    bot.run(BOT_TOKEN)

thread = threading.Thread(target=run_bot, daemon=True)
thread.start()
