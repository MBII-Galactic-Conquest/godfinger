import logging;
import godfingerEvent;
import pluginExports;
import lib.shared.serverdata as serverdata
import subprocess
import json
import os
import time
import shutil
import requests
import threading
from dotenv import load_dotenv, set_key

## Requires that your REPOSITORY is publicly visible ##

CONFIG_FILE = "gtConfig.json"
PLACEHOLDER = "placeholder"
PLACEHOLDER_REPO = "placeholder/placeholder"
PLACEHOLDER_BRANCH = "placeholder"
GITHUB_API_URL = "https://api.github.com/repos/{}/commits?sha={}"

class gitTrackerPlugin(object):
    def __init__(self, serverData) -> None:
        self._serverData = serverData
        self._messagePrefix = colors.ColorizeText("[GT]", "lblue") + ": "

# Check if the system is Windows
def OSGitCheck():
    if os.name == 'nt':  # Windows
        GIT_PATH = shutil.which("git")

        if GIT_PATH is None:
            GIT_PATH = os.path.abspath(os.path.join("..", "..", "..", "venv", "GIT", "bin"))
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

def check_git_installed():
    global GIT_EXECUTABLE
    if shutil.which("git") or os.path.exists(GIT_EXECUTABLE):
        try:
            subprocess.run([GIT_EXECUTABLE, "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print("[INFO] Git is installed.")
            return True
        except subprocess.CalledProcessError:
            print("[ERROR] Git version check failed.")
            return False
    else:
        print("[ERROR] Git is not installed.")
        exit(0)

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
            "refresh_interval": 60
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
    refresh_interval = config.get("refresh_interval", 60)

    for repo in repositories:
        if repo["repository"] == PLACEHOLDER or repo["branch"] == PLACEHOLDER:
            print("\nPlaceholders detected in gtConfig.json. Please update the file.")
            input("Press Enter to exit...")
            exit(1)

    return repositories, refresh_interval

def get_env_file_name(repo_url, branch_name):
    repo_name = repo_url.split('/')[-1]
    return f"{repo_name}_{branch_name}.env"

def load_or_create_env(repo_url, branch_name):
    env_dir = os.path.join(os.getcwd(), "env")
    if not os.path.exists(env_dir):
        os.makedirs(env_dir)

    # Ensure each repository gets its own .env file
    env_file = get_env_file_name(repo_url, branch_name)
    env_file_path = os.path.join(env_dir, env_file)

    if not os.path.exists(env_file_path):
        print(f"Creating .env file: {env_file_path}")
        # Create new .env file with placeholders
        set_key(env_file_path, "last_hash", "")
        set_key(env_file_path, "last_message", "")
        last_hash, last_message = "", ""  # Placeholder values if new
    else:
        print(f".env file exists: {env_file_path}")
    
    # Load existing .env data
    load_dotenv(env_file_path)
    last_hash = os.getenv("last_hash", "")
    last_message = os.getenv("last_message", "")
    
    return last_hash, last_message, env_file_path

def update_env_file_if_needed(repo_url, branch_name, commit_hash, commit_message):
    global PluginInstance
    # First, reset last_hash and last_message
    last_hash, last_message, env_file_path = load_or_create_env(repo_url, branch_name)
    
    # Trim whitespace from the values
    commit_hash = commit_hash.strip()
    commit_message = commit_message.strip()
    last_hash = last_hash.strip() if last_hash else ""
    last_message = last_message.strip() if last_message else ""

    print(f"Comparing commit info for {repo_url} ({branch_name}):")
    print(f"Last commit hash: {last_hash}")
    print(f"Last commit message: {last_message}")
    print(f"New commit hash: {commit_hash}")
    print(f"New commit message: {commit_message}")
    
    # Check if the commit hash or message has changed for this specific repository
    if last_hash != commit_hash or last_message != commit_message:
        print(f"Updating .env file for {repo_url} ({branch_name}) with new commit (Hash: {commit_hash}, Message: {commit_message})")
        # Only update if hash or message has changed
        set_key(env_file_path, "last_hash", commit_hash)
        set_key(env_file_path, "last_message", commit_message)
        PluginInstance._serverData.rcon.say(PluginInstance._messagePrefix + f"^5{commit_hash} ^7{repo_url} - ^5{commit_message}")
    else:
        print(f"No changes for {repo_url} ({branch_name}). Commit (Hash: {commit_hash}, Message: {commit_message}) is the same as the last one.")

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
        
        print(f"Requesting commit info from GitHub API for {repo_name}, branch '{branch}'...")

        response = requests.get(api_url)

        if response.status_code == 403:
            print(response.headers.get('X-RateLimit-Remaining'))

        if response.status_code == 200:
            commit_data = response.json()[0]
            commit_hash = commit_data["sha"][:7]
            commit_message = commit_data["commit"]["message"]
            return commit_hash, commit_message
        else:
            print(f"Error: Failed to fetch commit info from GitHub API. Status code {response.status_code}")
            return None, None
    except requests.RequestException as e:
        print(f"Error: Could not retrieve commit info for {repo_url} on branch '{branch}'. {str(e)}")
        return None, None

def monitor_commits():
    repositories, refresh_interval = load_config()
    
    if not repositories:
        print("No repositories found in gtConfig.json.")
        return
    
    try:
        while True:
            print("Starting commit check loop...")
            for i, repo in enumerate(repositories, 1):
                print(f"Checking repository {i}: {repo['repository']} on branch {repo['branch']}")
                repo_url = repo["repository"]
                branch_name = repo["branch"]

                commit_hash, commit_message = get_latest_commit_info(repo_url, branch_name)

                if commit_hash and commit_message:
                    print(f"\nNew commit detected for repository {i} ('{branch_name}') in '{repo_url}':")
                    print(f"Hash: {commit_hash}")
                    print(f"Message: {commit_message}")

                    update_env_file_if_needed(repo_url, branch_name, commit_hash, commit_message)

            print("Sleeping...")
            time.sleep(refresh_interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")

def start_monitoring():
    monitoring_thread = threading.Thread(target=monitor_commits)
    monitoring_thread.daemon = True
    monitoring_thread.start()

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
    OSGitCheck()
    create_config_placeholder()
    check_git_installed()
    start_monitoring()
    startTime = time()
    loadTime = time() - startTime
    PluginInstance._serverData.rcon.say(PluginInstance._messagePrefix + f"Git Tracker started in {loadTime:.2f} seconds!")
    return True; # indicate plugin start success

# Called each loop tick from the system, TODO? maybe add a return timeout for next call
def OnLoop():
    pass

# Called before plugin is unloaded by the system, finalize and free everything here
def OnFinish():
    global PluginInstance
    del PluginInstance;
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
