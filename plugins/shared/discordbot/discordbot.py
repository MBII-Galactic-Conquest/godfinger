import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import threading
import logging
import asyncio
import discord
import os
import time
import re
from dotenv import load_dotenv
from datetime import datetime

# Initialize the Logger
Log = logging.getLogger(__name__)

# Global variables
SERVER_DATA = None
BIGDATA_LOG = None
last_position = 0  # Tracks the last read position of the log file
last_sent_message = ""  # Store the last sent message to prevent re-sending
bot_thread = None
shutdown_event = threading.Event()
log_watcher_task = None

# Define intents to specify what events the bot will listen to
intents = discord.Intents.default()
intents.message_content = True  # To read message content (required for message-based commands)
intents.members = True  # To listen to member join/leave events

# Initialize the Discord client with intents
client = discord.Client(intents=intents)

# Environmental variables
# https://discord.com/developers/
DISCORD_BOT_TOKEN = None
DISCORD_GUILD_ID = None
DISCORD_CHANNEL_ID = None
DISCORD_THREAD_ID = None
ADMIN_ROLE_ID = None
USE_THREAD = False

class discordBotPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData : serverdata.ServerData = serverData
        self._messagePrefix = colors.ColorizeText("[DISC]", "lblue") + ": "

# Load environment variables
def load_env_variables():
    global DISCORD_BOT_TOKEN, DISCORD_GUILD_ID, DISCORD_CHANNEL_ID, DISCORD_THREAD_ID, USE_THREAD, ADMIN_ROLE_ID
    env_file = os.path.join(os.path.dirname(__file__), "discordbot.env")
    if not os.path.exists(env_file):
        print(f"{env_file} not found. Creating one...")
        with open(env_file, 'w') as f:
            f.write("""DISCORD_BOT_TOKEN=your_token_here
DISCORD_GUILD_ID=your_guild_id_here
DISCORD_CHANNEL_ID=your_channel_id_here
DISCORD_THREAD_ID=your_thread_id_here  # Optional, used only if USE_THREAD is True
ADMIN_ROLE_ID=your_admin_role_id_here # Optional, however will flag errors when !admin is used without.
USE_THREAD=True  # Set this to True to use threads, or False to use channels
""")
        print(f"{env_file} has been created!")
    else:
        print(f"{env_file} already exists, proceeding.")

    if load_dotenv(env_file):
        DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
        DISCORD_GUILD_ID = os.getenv("DISCORD_GUILD_ID")
        DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
        DISCORD_THREAD_ID = os.getenv("DISCORD_THREAD_ID")
        ADMIN_ROLE_ID = os.getenv("ADMIN_ROLE_ID")
        USE_THREAD = os.getenv("USE_THREAD", "False").lower() == "true"
        print("Required environmental variables for Discord loaded successfully!")
    else:
        print("Unable to load environmental variables! Ensure discordbot.env exists!")

# Called once when this module (plugin) is loaded
def OnInitialize(serverData: serverdata.ServerData, exports=None) -> bool:
    global SERVER_DATA
    print("Initializing discordbot plugin!")
    SERVER_DATA = serverData  # Store server data

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
    global BIGDATA_LOG
    BIGDATA_LOG = serverData.args.logfile
    # Load environment variables
    load_env_variables()

    if exports is not None:
        pass  # Export data if needed

    global PluginInstance
    PluginInstance = discordBotPlugin(serverData)

    return True  # Indicate plugin load success

# Called once when the platform starts
def OnStart():
    global bot_thread
    if DISCORD_BOT_TOKEN and DISCORD_BOT_TOKEN.lower() != "your_token_here":
        # Start Discord bot in a separate thread to avoid blocking the main application
        bot_thread = threading.Thread(target=start_discord_bot_thread, daemon=True)
        bot_thread.start()
        print("Discord bot thread started!")
    else:
        print("Discord bot token is missing. Bot will not start.")
    return True

# Function to start the Discord bot
async def start_discord_bot():
    await client.start(DISCORD_BOT_TOKEN)

# Start Discord bot in a separate thread
def start_discord_bot_thread():
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # Run the Discord bot until it completes (e.g., disconnects)
    try:
        loop.run_until_complete(client.start(DISCORD_BOT_TOKEN))
    except Exception as e:
        print(f"Error starting Discord bot: {e}")
    finally:
        loop.run_until_complete(client.close())
        loop.stop()
        loop.close()

def stop_bot_thread():
    global bot_thread
    if bot_thread and bot_thread.is_alive():
        Log.info("Signaling Discord bot thread to shut down...")
        shutdown_event.set()  # Signal the log watcher to stop

        if log_watcher_task:
            Log.info("Cancelling log watcher task...")
            # Schedule cancellation on the client's event loop
            future_cancel = asyncio.run_coroutine_threadsafe(log_watcher_task.cancel(), client.loop)
            try:
                future_cancel.result(timeout=1) # Wait briefly for cancellation
                Log.info("Log watcher task cancelled.")
            except asyncio.TimeoutError:
                Log.error("Timed out waiting for log watcher task to cancel.")
            except Exception as e:
                Log.error(f"Error during log watcher cancellation: {e}")
            log_watcher_task = None

        future = asyncio.run_coroutine_threadsafe(client.close(), client.loop)
        try:
            future.result(timeout=5)  # Wait for the client to close with a timeout
        except asyncio.TimeoutError:
            Log.error("Timed out waiting for bot client to close gracefully.")
        except Exception as e:
            Log.error(f"Error during bot shutdown: {e}")
        bot_thread.join(timeout=5)  # Wait for the thread to finish
        if bot_thread.is_alive():
            Log.debug("Warning: Discord bot thread did not terminate.")
        else:
            Log.info("Discord bot thread has been shut down.")
        bot_thread = None

# Asynchronous function to monitor the bigdata.log file for new lines
async def async_watch_bigdata_log():
    global last_position, last_sent_message
    while True:
        try:
            with open(BIGDATA_LOG, 'r') as log_file:
                log_file.seek(last_position)  # Move to the last known position
                new_lines = log_file.readlines()
                last_position = log_file.tell()  # Update the position

            if new_lines:
                message = ''.join(new_lines).strip()
                # Filter out messages that contain "discord" or "https"
                filtered_message = filter_message(message)

                # Only send new lines (i.e., additions to the log)
                if filtered_message and filtered_message != last_sent_message:
                    last_sent_message = filtered_message  # Store the latest message sent
                    await send_to_discord(filtered_message)

        except FileNotFoundError:
            print(f"{BIGDATA_LOG} not found. Waiting for the file to be created...")
        except Exception as e:
            print(f"Error monitoring log file: {e}")

        await asyncio.sleep(1)  # Poll every 1 second asynchronously

# Event handler for when the bot is ready
@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')
    # Start the asynchronous log watcher as a background task
    asyncio.create_task(async_watch_bigdata_log())
    log_watcher_task = asyncio.create_task(async_watch_bigdata_log())

# Function to filter out Discord or HTTP-related lines
def filter_message(message):
    # Regular expression to match HTTP URLs and 'discord'
    if re.search(r'https?://|discord', message, re.IGNORECASE):
        return ""  # Return an empty string if the message contains discord or URLs
    if re.search(r'urllib3.connectionpool', message, re.IGNORECASE):
        return "" # Return an empty string if the message contains url requests
    return message

# Send a message to a Discord thread or channel, ensuring it's within the 2000/4000 character limit
async def send_to_discord(message):
    try:
        if not message:
            return  # Skip sending if the message is empty (filtered out)

        # Ensure the bot is connected and ready
        if not client.is_ready():
            print("Bot is not connected or not ready yet.")
            return

        # Get the guild (server) by ID
        guild = client.get_guild(int(DISCORD_GUILD_ID))
        if guild is None:
            print(f"Error: Guild with ID {DISCORD_GUILD_ID} not found.")
            return

        # Determine the character limit
        char_limit = 2000

        # Split the message into chunks that fit within the character limit
        parts = await split_message(message, char_limit)

        # Send all parts
        for part in parts:
            await send_part_to_discord(part)

    except Exception as e:
        print(f"An error occurred while sending the message: {e}")

# Recursive function to split the message into parts
async def split_message(message, char_limit):
    parts = []
    while len(message) > char_limit:
        # Find the last possible newline or space before the character limit to avoid cutting off words
        split_index = message.rfind('\n', 0, char_limit)
        if split_index == -1:  # No newline found, use space
            split_index = message.rfind(' ', 0, char_limit)
            if split_index == -1:  # No space found, force split at char_limit
                split_index = char_limit
        part = message[:split_index].strip()  # Get the part and remove any leading/trailing spaces
        parts.append(part)
        message = message[split_index:].lstrip()  # Remove the part we just sent and trim spaces

    # If there's any leftover message that's less than the limit, add it as the last part
    if message:
        parts.append(message)

    # Check if any part is still larger than the char_limit and split further if necessary
    for i in range(len(parts)):
        if len(parts[i]) > char_limit:
            # If the part is still too long, split it further recursively
            parts[i:i+1] = await split_message(parts[i], char_limit)

    return parts

async def send_part_to_discord(part):
    try:
        # Get the guild (server) by ID
        guild = client.get_guild(int(DISCORD_GUILD_ID))
        if guild is None:
            print(f"Error: Guild with ID {DISCORD_GUILD_ID} not found.")
            return

        # Check if the message contains !admin
        if '!admin' in part.lower():
            # If the message has !admin, send it without a code block
            # Will need svsay message to declare admins are informed. ::!IMPORTANT!::
            # Will need sleep timer until admin can be called again. ::!IMPORTANT!::
            message_to_send = f"<@&{ADMIN_ROLE_ID}>\n\n```{part}```"
        else:
            # Send in code block for readability
            message_to_send = f"```{part}```"

        if USE_THREAD:
            # Send to specific thread
            thread = guild.get_thread(int(DISCORD_THREAD_ID))
            if thread:
                await thread.send(message_to_send)  # Send without code block if !admin
                print(f"Message part sent to thread with ID {DISCORD_THREAD_ID}.")
            else:
                print(f"Error: Thread with ID {DISCORD_THREAD_ID} not found in guild.")
        elif DISCORD_CHANNEL_ID:
            # Send to main channel if no thread is used
            channel = guild.get_channel(int(DISCORD_CHANNEL_ID))
            if channel:
                await channel.send(message_to_send)  # Send without code block if !admin
                print(f"Message part sent to channel with ID {DISCORD_CHANNEL_ID}.")
            else:
                print(f"Error: Channel with ID {DISCORD_CHANNEL_ID} not found in guild.")
    except Exception as e:
        print(f"Error sending part to Discord: {e}")

# Called each loop tick from the system
def OnLoop():
    pass

# Called before the plugin is unloaded by the system
def OnFinish():
    stop_bot_thread()
    pass

# Called from the system on some event raising
def OnEvent(event) -> bool:
    return False
