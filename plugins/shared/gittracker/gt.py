import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import lib.shared.colors as colors
import subprocess
import json
import sys
import os
import time
import shutil
import requests
import threading
from dotenv import load_dotenv, set_key

SERVER_DATA = None;
GODFINGER = "godfinger"
Log = logging.getLogger(__name__);

## Requires that your REPOSITORY is publicly visible ##

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "gtConfig.json");
PLACEHOLDER = "placeholder"
PLACEHOLDER_REPO = "placeholder/placeholder"
PLACEHOLDER_BRANCH = "placeholder"
GITHUB_API_URL = "https://api.github.com/repos/{}/commits?sha={}"

UPDATE_NEEDED = False
FALSE_VAR = "False"

if os.name == 'nt':  # Windows
    GIT_PATH = shutil.which("git")

    if GIT_PATH is None:
        GIT_PATH = os.path.abspath(os.path.join("venv", "GIT", "bin"))
        GIT_EXECUTABLE = os.path.abspath(os.path.join(GIT_PATH, "git.exe"))
    else:
        GIT_EXECUTABLE = os.path.abspath(GIT_PATH)

    PYTHON_CMD = "python"  # On Windows, just use 'python'

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        print(f"Git executable set to: {GIT_EXECUTABLE}")
    else:
        print("Git executable could not be set. Ensure Git is installed.")

else:  # Non-Windows (Linux, macOS)
    GIT_EXECUTABLE = shutil.which("git")
    PYTHON_CMD = "python3" if shutil.which("python3") else "python"

    if GIT_EXECUTABLE:
        os.environ["GIT_PYTHON_GIT_EXECUTABLE"] = GIT_EXECUTABLE
        print(f"Git executable set to default path: {GIT_EXECUTABLE}")
    else:
        print("Git executable not found on the system.")

class gitTrackerPlugin(object):
    def __init__(self, serverData : serverdata.ServerData) -> None:
        self._serverData : serverdata.ServerData = serverData
        self._messagePrefix = colors.ColorizeText("[GT]", "lblue") + ": "

def check_git_installed():
    global GIT_EXECUTABLE
    if shutil.which("git") or os.path.exists(GIT_EXECUTABLE):
        try:
            subprocess.run([GIT_EXECUTABLE, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("[GT] Git is installed.")
            return True
        except subprocess.CalledProcessError:
            print("[GT] Git version check failed.")
            return False
    else:
        print("[ERROR] Git is not installed.")
        sys.exit(0)

def create_config_placeholder():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "repositories": [
                {
                    "repository": PLACEHOLDER_REPO,
                    "branch": PLACEHOLDER_BRANCH
                },
                {
                    "repository": PLACEHOLDER_REPO,
                    "branch": PLACEHOLDER_BRANCH
                }
            ],
            "refresh_interval": 60,
            "gfBuildBranch": PLACEHOLDER_BRANCH,
            "isGFBuilding": FALSE_VAR
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"Created {CONFIG_FILE} with placeholder repositories.")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: Config file '{CONFIG_FILE}' not found.")
        return None, None

    with open(CONFIG_FILE, "r") as f:
        config = json.load(f)

    repositories = config.get("repositories", [])
    refresh_interval = config.get("refresh_interval")
    gfBuildBranch = config.get("gfBuildBranch")
    isGFBuilding = config.get("isGFBuilding")

    for repo in repositories:
        if repo["repository"] == PLACEHOLDER or repo["branch"] == PLACEHOLDER:
            print("\nPlaceholders detected in gtConfig.json. Please update the file.")
            sys.exit(0)

    return repositories, refresh_interval

def get_env_file_name(repo_url, branch_name):
    repo_name = repo_url.split('/')[-1]
    return f"{repo_name}_{branch_name}.env"

def load_or_create_env(repo_url, branch_name):
    env_dir = os.path.join(os.path.dirname(__file__), "env")
    if not os.path.exists(env_dir):
        os.makedirs(env_dir)

    # Ensure each repository gets its own .env file
    env_file = get_env_file_name(repo_url, branch_name)
    env_file_path = os.path.join(env_dir, env_file)

    if not os.path.exists(env_file_path):
        Log.info(f"Creating .env file: {env_file_path}")
        # Create new .env file with placeholders
        set_key(env_file_path, "last_hash", "")
        set_key(env_file_path, "last_message", "")
        last_hash, last_message = "", ""  # Placeholder values if new
    else:
        Log.info(f".env file exists: {env_file_path}")
    
    # Load existing .env data
    load_dotenv(env_file_path)
    last_hash = os.getenv("last_hash", "")
    last_message = os.getenv("last_message", "")
    
    return last_hash, last_message, env_file_path

def update_env_file_if_needed(repo_url, branch_name, commit_hash, commit_message, isGFBuilding, gfBuildBranch):
    global PluginInstance
    # First, reset last_hash and last_message
    last_hash, last_message, env_file_path = load_or_create_env(repo_url, branch_name)
    repo_name = repo_url.replace("MBII-Galactic-Conquest/", "").replace("MBII-Galactic-Conquest/", "")
    
    # Trim whitespace from the values
    commit_hash = commit_hash.strip()
    commit_message = commit_message.strip()
    last_hash = last_hash.strip() if last_hash else ""
    last_message = last_message.strip() if last_message else ""

    Log.info(f"Comparing commit info for {repo_url} ({branch_name}):")
    Log.info(f"Last commit hash: {last_hash}")
    Log.info(f"Last commit message: {last_message}")
    Log.info(f"New commit hash: {commit_hash}")
    Log.info(f"New commit message: {commit_message}")
    
    # Check if the commit hash or message has changed for this specific repository
    if last_hash != commit_hash or last_message != commit_message:
        Log.info(f"Updating .env file for {repo_url} ({branch_name}) with new commit (Hash: {commit_hash}, Message: {commit_message})")
        # Only update if hash or message has changed
        set_key(env_file_path, "last_hash", commit_hash)
        set_key(env_file_path, "last_message", commit_message)
        full_message = f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5{commit_message}"
        if len(full_message) > 131:
            max_commit_message_length = 131 - len(f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5") - 3
            commit_message = commit_message[:max_commit_message_length] + "..."
            full_message = f"^5{commit_hash} ^7- {repo_name}/{branch_name} - ^5{commit_message}"
        PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + full_message)
        if isGFBuilding == True and GODFINGER in repo_name and gfBuildBranch in branch_name:
            PluginInstance._serverData.interface.SvSay(PluginInstance._messagePrefix + "Godfinger change detected, applying when all players leave the server...")
            deploy_hash = commit_hash
            deploy_message = commit_message
            UPDATE_NEEDED = True
    else:
        Log.info(f"No changes for {repo_url} ({branch_name}). Commit (Hash: {commit_hash}, Message: {commit_message}) is the same as the last one.")

    # Reset the values after processing to ensure no state leakage for the next repository
    last_hash = None
    last_message = None

    # Optionally, clear out environment variables to prevent interference between repository checks
    os.environ.pop("last_hash", None)
    os.environ.pop("last_message", None)

def get_latest_commit_info(repo_url: str, branch: str):
    try:
        repo_name = repo_url.replace("https://github.com/", "").replace("http://github.com/", "")
        api_url = GITHUB_API_URL.format(repo_name, branch)
        
        Log.info(f"Requesting commit info from GitHub API for {repo_name}, branch '{branch}'...")

        response = requests.get(api_url)

        if response.status_code == 403:
            Log.info(response.headers.get('X-RateLimit-Remaining'))

        if response.status_code == 200:
            commit_data = response.json()[0]
            commit_hash = commit_data["sha"][:7]
            commit_message = commit_data["commit"]["message"]
            return commit_hash, commit_message
        else:
            Log.info(f"Error: Failed to fetch commit info from GitHub API. Status code {response.status_code}")
            return None, None
    except requests.RequestException as e:
        Log.info(f"Error: Could not retrieve commit info for {repo_url} on branch '{branch}'. {str(e)}")
        return None, None

def monitor_commits():
    repositories, refresh_interval = load_config()
    
    if not repositories:
        print("No repositories found in gtConfig.json.")
        return
    
    try:
        while True:
            Log.info("Starting commit check loop...")
            for i, repo in enumerate(repositories, 1):
                Log.info(f"Checking repository {i}: {repo['repository']} on branch {repo['branch']}")
                repo_url = repo["repository"]
                branch_name = repo["branch"]

                commit_hash, commit_message = get_latest_commit_info(repo_url, branch_name)

                if commit_hash and commit_message:
                    Log.info(f"\nNew commit detected for repository {i} ('{branch_name}') in '{repo_url}':")
                    Log.info(f"Hash: {commit_hash}")
                    Log.info(f"Message: {commit_message}")

                    update_env_file_if_needed(repo_url, branch_name, commit_hash, commit_message)

            time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

def start_monitoring():
    monitoring_thread = threading.Thread(target=monitor_commits)
    monitoring_thread.daemon = True
    monitoring_thread.start()

def check_and_trigger_update(repo_name, branch_name, commit_hash, deploy_hash, gfBuildBranch, isGFBuilding):

    if isGFBuilding == True and UPDATE_NEEDED == True and commit_hash == deploy_hash and GODFINGER in repo_name and branch_name == gfBuildBranch:
        Log.info("Godfinger change detected with isGFBuilding enabled. Triggering update...")

        # Command to run update.py in a new window
        update_script = os.path.abspath("./update/update.py")

        # Define simulated inputs for update.py
        simulated_inputs = ["Y", "N", deploy_hash, ""]
        input_string = "\n".join(simulated_inputs) + "\n"

        # Launch subprocess with simulated input
        process = subprocess.Popen(
            [PYTHON_CMD, update_script],  # Run the script
            stdin=subprocess.PIPE,  # Provide input
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Use text mode for I/O
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0  # Open new window (Windows)
        )

        # Send input to the script
        process.communicate(input=input_string)
        Log.info("Update script executed with predefined inputs. Ensure godfinger autorestarting is on in godfingerCfg.json")
        time.sleep(5) # Sleeping to ensure everything works as intended
        print(0/0) # Crashing godfinger to force restart after update
    else:
        pass;

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
    PluginInstance = gitTrackerPlugin(serverData)

    return True; # indicate plugin load success

# Called once when platform starts, after platform is done with loading internal data and preparing
def OnStart():
    global PluginInstance
    create_config_placeholder()
    check_git_installed()
    start_monitoring()
    startTime = time.time()
    loadTime = time.time() - startTime
    PluginInstance._serverData.interface.Say(PluginInstance._messagePrefix + f"Git Tracker started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    pass;

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
        check_and_trigger_update()
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
